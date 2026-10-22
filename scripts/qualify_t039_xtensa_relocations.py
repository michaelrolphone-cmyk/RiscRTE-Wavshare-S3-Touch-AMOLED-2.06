#!/usr/bin/env python3
"""Host execution of pinned production Xtensa relocation, never target execution."""
import argparse
from collections import Counter
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
PARENT = '30ef8d4fbe7bf63072c72988e3711880672d1196'
RUNTIME = 'b7803e6d32ce08fb4060730acc5443416b30148c'
HELPER = '74f7491dc470b92dfa41fce41bf0c500f3714a94'
SDK = 'fff9895c82d744c7237be8847347bdd1b07c6643'
ADDITIONS = {'scripts/qualify_t039_xtensa_relocations.py', 'tests/t039-relocation/runner.c',
             'tests/test_t039_xtensa_relocations.py', 'docs/t039/relocation/README.md',
             '.github/workflows/t039-xtensa-relocation.yml'}
SLOTS = {'.text': 0, '.bss': 1, '.data': 2, '.rodata': 3, '.data.rel.ro': 4}
BASELINE_ELF = {'bytes': 154028, 'sha256': 'b3f4633d8bc0d0612d6410eae3f41d8c66a0586025f076a26dd0f277cac7232d'}
SDK_BLOBS = {'soc.h': '8588770c3cfba9c994230c453dacc2a1bd2ffce3',
             'esp_idf_version.h': '6a5c781e86f3c78e05234928d5f329e72fbe29c3'}
SOURCES = ['esp_elf.c', 'esp_elf_validate.c', 'esp_elf_adapter.c',
           'arch/esp_elf_xtensa.c', 'dlso/dlmod.c', 'dlso/dlfcn.c', 'esp_privileged_os_cpu.c']
FLAGS = ['CONFIG_IDF_TARGET_ESP32S3', 'CONFIG_ELF_LOADER_BUS_ADDRESS_MIRROR',
         'CONFIG_ELF_DYNAMIC_LOAD_SHARED_OBJECT', 'CONFIG_ELF_LOADER_CACHE_OFFSET', 'CONFIG_ELF_LOADER_LOAD_PSRAM']
LABELS = ['first', 'second', 'second-after-close', 'reloaded', 'after-failures']


def require(ok, message):
    if not ok:
        raise ValueError(message)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def record(data):
    return {'bytes': len(data), 'sha256': digest(data)}


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(data if isinstance(data, str) else json.dumps(data, sort_keys=True, indent=2) + '\n')


def git(root, *args):
    return subprocess.check_output(['git', '-C', str(root), *args]).decode().strip()


def source_guard(expected=None):
    head = git(ROOT, 'rev-parse', 'HEAD')
    require(not git(ROOT, 'status', '--porcelain'), 'Dirty source checkout')
    require(expected is None or expected == head, 'Wrong source head')
    changes = git(ROOT, 'diff', '--name-status', PARENT, head).splitlines()
    require(changes and all(r.startswith('A\t') and r[2:] in ADDITIONS for r in changes),
            'Only additive relocation qualification files are permitted above unchanged PR26')
    return head


def elf(data):
    from elftools.elf.elffile import ELFFile
    e = ELFFile(io.BytesIO(data))
    require(e.elfclass == 32 and e.little_endian and e['e_machine'] == 'EM_XTENSA' and e['e_type'] == 'ET_DYN', 'Not a 32-bit Xtensa dynamic ELF')
    return e


def model(data):
    """Parse independent expectations from ELF, never the loader's C structs."""
    e = elf(data)
    sections = {s.name: s for s in e.iter_sections() if s.name in SLOTS and s['sh_size']}
    relocations = []
    for section in e.iter_sections():
        if section['sh_type'] != 'SHT_RELA':
            continue
        symbols = e.get_section(section['sh_link'])
        for r in section.iter_relocations():
            sym = symbols.get_symbol(r['r_info_sym'])
            relocations.append({'site': r['r_offset'], 'type': r['r_info_type'],
                                'addend': r['r_addend'], 'name': sym.name,
                                'symbol_value': sym['st_value'], 'defined': sym['st_shndx'] != 'SHN_UNDEF'})
    require(len({r['site'] for r in relocations}) == len(relocations), 'Duplicate relocation sites not supported by independent oracle')
    require({r['type'] for r in relocations} <= {2, 4, 5}, 'Unexpected baseline/candidate relocation class')
    exports = {s.name: {'value': s['st_value'], 'kind': s['st_info']['type']}
               for s in e.get_section_by_name('.dynsym').iter_symbols()
               if s['st_info']['bind'] == 'STB_GLOBAL' and s['st_shndx'] != 'SHN_UNDEF'
               and s['st_info']['type'] in ('STT_FUNC', 'STT_OBJECT')}
    require(all(s['kind'] == 'STT_FUNC' for s in exports.values()), 'Unqualified new object exports')
    return e, sections, relocations, exports


def check_dump(data, exports, folder, label):
    """Whole-section byte oracle; no esp_elf_map_sym/elf_remap_text calls."""
    e, sections, rows, symbols = model(data)
    observed = json.loads((folder / (label + '.json')).read_bytes())
    require(len(observed['sections']) == 5, 'Missing section observations')
    addresses = {}
    for name, s in sections.items():
        slot = SLOTS[name]; o = observed['sections'][slot]
        require(o['slot'] == slot and o['virtual'] == s['sh_addr'] and o['size'] == s['sh_size'] and o['offset'] == s['sh_offset'], 'Section metadata mismatch: ' + name)
        require(0x3c000000 <= o['address'] < o['address'] + o['size'] <= 0x3e000000, 'Not a low 32-bit S3 D-bus mapping')
        addresses[name] = o['address']
    require(addresses['.text'] == observed['ptext'], 'Text allocation mismatch')
    cursor = observed['pdata']
    # Find first admissible congruent placement independently by enumeration,
    # rather than copying esp_elf_data_place's modular bitwise formula.
    for name in ('.data', '.rodata', '.data.rel.ro', '.bss'):
        s = sections.get(name)
        if s is None:
            continue
        alignment = max(4, s['sh_addralign'])
        while cursor % alignment != s['sh_addr'] % alignment:
            cursor += 1
        require(addresses[name] == cursor, 'Data placement mismatch: ' + name)
        cursor += s['sh_size']
    expected_request = sum(s['sh_size'] + max(4, s['sh_addralign']) - 1 for n, s in sections.items() if n != '.text')
    require(observed['data_request'] == expected_request and observed['text_request'] == sections['.text']['sh_size'], 'Mapping demand changed')
    require(cursor <= observed['pdata'] + expected_request, 'Data layout exceeds allocation')

    def locate(address, width=1):
        matches = [(n, s) for n, s in sections.items() if s['sh_addr'] <= address and address + width <= s['sh_addr'] + s['sh_size']]
        require(len(matches) == 1, 'Unmappable or overlapping virtual address')
        return matches[0]

    def mapped(address, instruction=True):
        name, s = locate(address)
        return addresses[name] + address - s['sh_addr'] + (0x06000000 if instruction and name == '.text' else 0)

    expected = {name: bytearray(s.data()) for name, s in sections.items()}
    text_targets = 0
    for r in rows:
        name, s = locate(r['site'], 4); offset = r['site'] - s['sh_addr']
        original = int.from_bytes(s.data()[offset:offset+4], 'little')
        if r['type'] == 2:
            continue
        if r['type'] == 5:
            value = mapped(original) if original else 0
            if original and locate(original)[0] == '.text':
                text_targets += 1
        else:
            # These fixtures' JMP_SLOT relocations are undefined imports or
            # defined symbols with a nonzero virtual address, never sentinels.
            if r['symbol_value']:
                value = mapped(r['symbol_value'])
            else:
                require(r['name'] in exports, 'Import absent from released public export table')
                value = exports[r['name']]
        expected[name][offset:offset+4] = value.to_bytes(4, 'little')
    for name, content in expected.items():
        require((folder / f'{label}-{SLOTS[name]}.bin').read_bytes() == content, 'Relocated section bytes differ: ' + name)
    require(observed['entry'] == mapped(e['e_entry']), 'Entry address differs')
    require(observed['exports'] == {name: mapped(s['value']) for name, s in symbols.items()}, 'Export addresses differ')
    return {'relocations': dict(sorted(Counter(str(r['type']) for r in rows).items())),
            'text_alias_targets': text_targets, 'exports': len(symbols),
            'mapping_request_bytes': observed['text_request'] + observed['data_request'],
            'bss_bytes': sections['.bss']['sh_size']}


def stubs(folder, sdkconfig, sdk_headers):
    for name, wanted in SDK_BLOBS.items():
        b = (sdk_headers / name).read_bytes()
        require(hashlib.sha1(b'blob ' + str(len(b)).encode() + b'\0' + b).hexdigest() == wanted, 'SDK header differs: ' + name)
    text = sdkconfig.decode()
    for flag in FLAGS:
        require(re.search(r'^#define ' + flag + r' 1$', text, re.M), 'Released config missing: ' + flag)
    require(not re.search(r'^#define CONFIG_ELF_LOADER_SET_MMU\b', text, re.M), 'Unexpected SET_MMU')
    write(folder / 'sdkconfig.h', text) # Complete released header, not selective test settings.
    write(folder / 'esp_idf_version.h', (sdk_headers / 'esp_idf_version.h').read_text())
    soc = (sdk_headers / 'soc.h').read_text()
    constants = '\n'.join(l for l in soc.splitlines() if re.match(r'#define SOC_[DI]ROM_(LOW|HIGH)\s', l))
    require(len(constants.splitlines()) == 4, 'SDK bus ranges missing')
    write(folder / 'soc/soc.h', '#pragma once\n' + constants + '\n')
    write(folder / 'soc/soc_caps.h', '#pragma once\n#define SOC_CACHE_INTERNAL_MEM_VIA_L1CACHE 0\n')
    write(folder / 'esp_attr.h', '#pragma once\n#define IRAM_ATTR\n#define DRAM_ATTR\n')
    write(folder / 'esp_heap_caps.h', '#pragma once\n#include <stddef.h>\n#define MALLOC_CAP_SPIRAM (1u<<10)\n#define MALLOC_CAP_8BIT (1u<<2)\nvoid *heap_caps_malloc(size_t, unsigned);\nvoid heap_caps_free(void *);\n')
    write(folder / 'esp32s3/rom/cache.h', '#pragma once\n#include <stdint.h>\nint Cache_WriteBack_Addr(uint32_t,uint32_t);\nint Cache_Invalidate_Addr(uint32_t,uint32_t);\n')
    write(folder / 'esp_log.h', '#pragma once\nstatic inline void log_model(const char *tag,const char *fmt,...){(void)tag;(void)fmt;}\n#define ESP_LOGE(...) log_model(__VA_ARGS__)\n#define ESP_LOGW(...) log_model(__VA_ARGS__)\n#define ESP_LOGI(...) log_model(__VA_ARGS__)\n#define ESP_LOGD(...) log_model(__VA_ARGS__)\n')
    write(folder / 'freertos/FreeRTOS.h', '''#pragma once
#include <stdint.h>
#include <pthread.h>
typedef uint32_t TickType_t;
typedef void *TaskHandle_t;
typedef pthread_mutex_t portMUX_TYPE;
typedef pthread_mutex_t StaticSemaphore_t;
typedef pthread_mutex_t *SemaphoreHandle_t;
#define portMUX_INITIALIZER_UNLOCKED PTHREAD_MUTEX_INITIALIZER
#define pdMS_TO_TICKS(ms) ((TickType_t)(ms))
#define pdTRUE 1
#define portMAX_DELAY UINT32_MAX
#define taskENTER_CRITICAL(m) pthread_mutex_lock(m)
#define taskEXIT_CRITICAL(m) pthread_mutex_unlock(m)
#define portENTER_CRITICAL(m) taskENTER_CRITICAL(m)
#define portEXIT_CRITICAL(m) taskEXIT_CRITICAL(m)
''')
    write(folder / 'freertos/task.h', '#pragma once\n#include "FreeRTOS.h"\nTickType_t xTaskGetTickCount(void);\nvoid vTaskDelay(TickType_t);\nTaskHandle_t xTaskGetCurrentTaskHandle(void);\n')
    write(folder / 'freertos/semphr.h', '''#pragma once
#include "FreeRTOS.h"
static inline SemaphoreHandle_t xSemaphoreCreateMutexStatic(StaticSemaphore_t *p){return pthread_mutex_init(p,0)==0?p:0;}
static inline int xSemaphoreTake(SemaphoreHandle_t p,TickType_t t){(void)t;return pthread_mutex_lock(p)==0;}
static inline int xSemaphoreGive(SemaphoreHandle_t p){return pthread_mutex_unlock(p)==0;}
''')


def run(args):
    head = source_guard()
    pins = json.loads((ROOT / 'docs/t039/product-candidate/source-pins.json').read_bytes())
    for path, pin in ((args.runtime, RUNTIME), (args.image_helper, HELPER)):
        require(git(path, 'rev-parse', 'HEAD') == pin and not git(path, 'status', '--porcelain'), 'Dependency source differs')
    for filename in ('sd-apps.zip', 'source-lock.json', 'evidence.zip'):
        key = 'Waveshare-0.1.64-SD-Apps-Evidence.zip' if filename == 'evidence.zip' else filename
        require(record((args.baseline / filename).read_bytes()) == pins['baseline_assets'][key], 'Released asset differs: ' + filename)
    lock = json.loads((args.baseline / 'source-lock.json').read_bytes())
    with zipfile.ZipFile(args.baseline / 'evidence.zip') as z:
        native = z.read('build/riscrte_native.elf'); sdkconfig = z.read('build/config/sdkconfig.h')
    for name, data in (('firmware_elf', native), ('sdkconfig_header', sdkconfig)):
        require(record(data) == {k: lock['native_files'][name][k] for k in ('bytes', 'sha256')}, 'Released evidence differs: ' + name)
    require(lock['sources']['sdk']['revision'] == SDK, 'SDK source changed')
    require(digest(args.utilities_archive.read_bytes()) == pins['utilities_archive_sha256'], 'Candidate archive differs')
    with zipfile.ZipFile(args.utilities_archive) as z:
        candidate = z.read('app/ble_buttons.elf')
    require(record(candidate) == pins['candidate_elf'], 'Candidate ELF differs')
    with zipfile.ZipFile(args.baseline / 'sd-apps.zip') as z:
        baseline = z.read('Apps/ble_buttons/ble_buttons.elf')
    require(record(baseline) == BASELINE_ELF, 'Baseline ELF differs')
    spec = importlib.util.spec_from_file_location('released_verify_update_elf', args.image_helper / 'scripts/verify_update_elf.py')
    helper = importlib.util.module_from_spec(spec); spec.loader.exec_module(helper)
    from elftools.elf.elffile import ELFFile
    exports = helper.public_exports(ELFFile(io.BytesIO(native)))
    require(not args.output.exists(), 'Output must be new')
    args.output.mkdir(parents=True)
    out = args.output
    q = {'schema': 1, 'source_commit': head, 'parent_source': PARENT, 'runtime': RUNTIME,
         'sdk': SDK, 'released_sdkconfig': record(sdkconfig), 'native_elf': record(native),
         'target_instructions_executed': False, 'live_allocator_fit_verified': False,
         'hardware_qualified': False, 'production_changed': False, 'results': {},
         'leak_sanitizer_enabled': not args.no_leak_sanitizer,
         'status': 'qualification-in-progress', 'ci': {k: os.getenv(k) for k in ('GITHUB_SHA', 'GITHUB_RUN_ID', 'GITHUB_RUN_ATTEMPT')}}
    write(out / 'released-public-exports.json', exports)
    stubs(out / 'sdk-model', sdkconfig, args.sdk_headers)
    try:
        for name, data in (('baseline-0.1.29', baseline), ('candidate-0.1.31', candidate)):
            folder = out / name; folder.mkdir(); (folder / 'input.elf').write_bytes(data)
            _, _, rows, _ = model(data)
            imports = sorted({r['name'] for r in rows if r['type'] == 4 and not r['defined']})
            require(imports and all(n in exports for n in imports), 'Unresolved import in released namespace')
            write(folder / 'released_exports.h', 'static const struct {const char *name; uintptr_t address;} released_exports[]={\n' +
                  ',\n'.join('{' + json.dumps(n) + ',' + str(v) + 'u}' for n, v in sorted(exports.items())) + '};\n' +
                  'static const char *required_imports[]={' + ','.join(json.dumps(n) for n in imports) + '};\n')
            q['results'][name] = {'input': record(data), 'imports': imports, 'runs': []}
            for mode in ('normal', 'sanitized'):
                work = folder / mode; work.mkdir()
                command = ['cc', '-std=c11', '-D_GNU_SOURCE', '-Wall', '-Wextra', '-Werror',
                           '-Wno-pointer-to-int-cast', '-Wno-int-to-pointer-cast', '-Wno-sign-compare', '-Wno-unused-parameter',
                           '-ffunction-sections', '-fdata-sections', '-Wl,--gc-sections', '-pthread',
                           '-DELF_LOADER_VER_MAJOR=1', '-DELF_LOADER_VER_MINOR=0', '-DELF_LOADER_VER_PATCH=0',
                           '-Ddlopen=t039_dlopen', '-Ddlsym=t039_dlsym', '-Ddlclose=t039_dlclose', '-Ddlerror=t039_dlerror',
                           '-I' + str(out / 'sdk-model'), '-I' + str(folder), '-I' + str(args.runtime / 'lib/elf_loader/include')]
                if mode == 'sanitized':
                    command += ['-fsanitize=address,undefined', '-fno-omit-frame-pointer', '-fno-pie', '-no-pie']
                # ASan global registration roots the otherwise unreachable privileged
                # inventory. Disable global instrumentation ONLY in the scope
                # translation unit so linker GC can discard unused provider
                # APIs; scope function bodies remain ASan/UBSan instrumented.
                scope = work / 'ordinary-scope.o'
                scope_command = command + (['--param=asan-globals=0'] if mode == 'sanitized' else []) + [
                    '-c', str(args.runtime / 'lib/elf_loader/src/esp_privileged_os_cpu.c'), '-o', str(scope)]
                write(work / 'scope-compile-command.json', scope_command)
                compiled = subprocess.run(scope_command, capture_output=True, text=True)
                write(work / 'scope-compile.log', compiled.stdout + compiled.stderr); compiled.check_returncode()
                command += [str(ROOT / 'tests/t039-relocation/runner.c'), str(scope)] + [
                    str(args.runtime / 'lib/elf_loader/src' / s) for s in SOURCES if s != 'esp_privileged_os_cpu.c']
                command += ['-o', str(work / 'runner')]
                write(work / 'compile-command.json', command)
                compiled = subprocess.run(command, capture_output=True, text=True)
                write(work / 'compile.log', compiled.stdout + compiled.stderr); compiled.check_returncode()
                env = dict(os.environ, ASAN_OPTIONS='detect_leaks=' + ('0' if args.no_leak_sanitizer else '1') + ':halt_on_error=1', UBSAN_OPTIONS='halt_on_error=1:print_stacktrace=1')
                result = subprocess.run([str(work / 'runner'), str(folder / 'input.elf'), str(work)], capture_output=True, text=True, env=env)
                write(work / 'run.log', result.stdout + result.stderr); result.check_returncode()
                observations = [check_dump(data, exports, work, label) for label in LABELS]
                require(all(o == observations[0] for o in observations), 'Repeated load outcomes differ')
                controls = json.loads((work / 'controls.json').read_bytes())
                require(controls['missing_import_failures'] == len(imports) and controls['remaining_allocations'] == 0 and
                        controls['real_relocation_failures'] == 3 and controls['cache_backend_failures'] == 2, 'Missing cleanup controls')
                q['results'][name]['runs'].append({'mode': mode, **observations[0], 'controls': controls})
        controls = subprocess.run([sys.executable, '-m', 'unittest', 'discover', '-s', str(ROOT / 'tests'),
                                   '-p', 'test_t039_xtensa_relocations.py', '-v'], capture_output=True, text=True,
                                  env=dict(os.environ, T039_RELOCATION_ARTIFACT=str(out)))
        write(out / 'oracle-controls.log', controls.stdout + controls.stderr); controls.check_returncode()
        require('Ran 12 tests' in controls.stderr and 'skipped=' not in controls.stderr, 'Oracle controls incomplete')
        q['oracle_mutation_rejections'] = 10
        source_guard(head)
        for path, pin in ((args.runtime, RUNTIME), (args.image_helper, HELPER)):
            require(git(path, 'rev-parse', 'HEAD') == pin and not git(path, 'status', '--porcelain'), 'Dependency changed during qualification')
        q['status'] = 'host-production-xtensa-relocation-qualified'
    except Exception as exc:
        q['status'] = 'qualification-failed'; q['failure'] = str(exc)
        raise
    finally:
        q['production_source_files'] = {s: record((args.runtime / 'lib/elf_loader/src' / s).read_bytes()) for s in SOURCES}
        q['inventory'] = {p.relative_to(out).as_posix(): record(p.read_bytes()) for p in sorted(out.rglob('*')) if p.is_file() and p.name != 'qualification.json'}
        write(out / 'qualification.json', q)
    print(json.dumps({'status': q['status'], 'source_commit': head, 'receipt_sha256': digest((out / 'qualification.json').read_bytes())}))


def verify(folder, source, receipt_sha):
    source_guard(source)
    require(digest((folder / 'qualification.json').read_bytes()) == receipt_sha, 'Receipt digest mismatch')
    receipt = json.loads((folder / 'qualification.json').read_bytes())
    require(receipt['source_commit'] == source and receipt['parent_source'] == PARENT and receipt['runtime'] == RUNTIME and receipt['sdk'] == SDK, 'Receipt source differs')
    for flag in ('target_instructions_executed', 'live_allocator_fit_verified', 'hardware_qualified', 'production_changed'):
        require(receipt[flag] is False, 'Scope claim changed')
    inventory = {}
    for p in sorted(folder.rglob('*')):
        require(not p.is_symlink(), 'Artifact symlink forbidden')
        if p.is_file() and p.name != 'qualification.json':
            inventory[p.relative_to(folder).as_posix()] = record(p.read_bytes())
    require(inventory == receipt['inventory'], 'Transported inventory changed')
    require(receipt['status'] in ('host-production-xtensa-relocation-qualified', 'qualification-failed'), 'Unknown qualification result')
    if receipt['status'] == 'qualification-failed':
        require(receipt.get('failure'), 'Missing preserved failure')
        return receipt
    require(receipt['oracle_mutation_rejections'] == 10, 'Oracle rejection controls missing')
    exports = json.loads((folder / 'released-public-exports.json').read_bytes())
    pins = json.loads((ROOT / 'docs/t039/product-candidate/source-pins.json').read_bytes())
    for name, wanted in (('baseline-0.1.29', BASELINE_ELF), ('candidate-0.1.31', pins['candidate_elf'])):
        row = receipt['results'][name]
        data = (folder / name / 'input.elf').read_bytes()
        require(record(data) == wanted == row['input'], 'Input identity mismatch')
        require([r['mode'] for r in row['runs']] == ['normal', 'sanitized'], 'Incomplete modes')
        for run in row['runs']:
            work = folder / name / run['mode']
            for label in LABELS:
                observed = check_dump(data, exports, work, label)
                require(all(run[k] == v for k, v in observed.items()), 'Receipt observations differ')
            controls = json.loads((work / 'controls.json').read_bytes())
            require(run['controls'] == controls and controls['remaining_allocations'] == 0 and
                    controls['allocation_failures'] == 9 and controls['reader_cleanup_failures'] == 1 and
                    controls['failed_second_allocation_cases'] == 9 and controls['real_relocation_failures'] == 3 and
                    controls['cache_backend_failures'] == 2 and controls['missing_import_failures'] == len(row['imports']) and
                    controls['target_instructions_executed'] is False, 'Cleanup controls differ')
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='action', required=True)
    build = commands.add_parser('build')
    for n in ('runtime', 'image-helper', 'baseline', 'utilities-archive', 'sdk-headers', 'output'):
        build.add_argument('--' + n, required=True, type=lambda s: Path(s).resolve())
    build.add_argument('--no-leak-sanitizer', action='store_true', help='Local ptrace fallback only; receipt records leak detection disabled. CI never uses this.')
    check = commands.add_parser('verify')
    check.add_argument('--artifact', type=Path, required=True)
    check.add_argument('--source-sha', required=True)
    check.add_argument('--receipt-sha256', required=True)
    args = parser.parse_args()
    if args.action == 'build':
        run(args)
    else:
        receipt = verify(args.artifact, args.source_sha, args.receipt_sha256)
        print('Transported relocation evidence verified: ' + receipt['status'])


if __name__ == '__main__':
    main()
