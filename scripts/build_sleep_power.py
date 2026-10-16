#!/usr/bin/env python3
"""Build only the source-pinned Waveshare power provider; compare two outputs."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import compact_cohort_elf
from normalize_xtensa_relocations import normalize
from package_sleep_rebound import require, record, sha


def build(product, watch, system, runtime, compiler, output):
    compiler = compiler.with_name('xtensa-esp32s3-elf-gcc')
    require(not output.exists(), 'Provider build output must be new')
    output.mkdir(parents=True)
    validator = output / 'validate-elf'
    subprocess.run(['cc', '-std=c11', '-Wall', '-Wextra', '-Werror', '-I'+str(system/'test/native_apps/stubs'),
        '-I'+str(system/'lib/elf_loader/include'), str(system/'lib/elf_loader/src/esp_elf_validate.c'),
        str(system/'test/native_apps/validate_test.c'), '-o', str(validator)], check=True)
    selected = {}
    for role, root, folders in [('watch',watch,['sdk/driver','sdk/app','include']),
                                ('runtime',runtime,['sdk/driver','sdk/app','sdk/hardware']),
                                ('product',product,['include'])]:
        for folder in folders:
            for f in sorted((root/folder).glob('*.h')):
                selected[f.name] = ({'role':role,'path':f.relative_to(root).as_posix(),'sha256':sha(f.read_bytes())},f.read_bytes())
    headers = {name:row for name,(row,_) in sorted(selected.items())}
    expected = json.loads((product/'docs/sleep-rebound/power-header-selection.json').read_text())
    require(headers == expected, 'Power provider public-header selection differs')
    sdk=output/'sdk';sdk.mkdir()
    for name,(_,raw) in selected.items(): (sdk/name).write_bytes(raw)
    include = [sdk]
    results = []
    for name in ('a', 'b'):
        root = output / name; root.mkdir()
        elf = root/'driver.elf'; exports = root/'exports.map'
        exports.write_text('{ global: t5_driver_get; local: *; };\n')
        command = [str(compiler), '-std=c11', '-Os', '-fPIC', '-mtext-section-literals', '-mlongcalls',
            '-fvisibility=hidden', '-ffreestanding', '-fno-builtin', '-nostdlib', '-nostartfiles', '-shared',
            '-Wl,--no-relax', '-Wl,--hash-style=sysv', '-Wl,--gc-sections', '-ffunction-sections', '-fdata-sections',
            '-Wl,--version-script='+str(exports), '-Wall', '-Wextra', '-Werror', '-Wno-misleading-indentation',
            *['-I'+str(x) for x in include], str(product/'drivers/power_axp2101/driver.c'), '-lgcc', '-o', str(elf)]
        subprocess.run(command, check=True)
        normalize(elf)
        compaction = compact_cohort_elf.compact(elf, str(compiler), debug_path=root/'uncompacted.elf')
        subprocess.run([str(validator), str(elf)], check=True)
        symbols = subprocess.check_output([str(compiler).removesuffix('gcc')+'nm', '-D', str(elf)], text=True)
        imports = {line.split()[-1] for line in symbols.splitlines() if ' U ' in ' '+line}
        exports_found = {line.split()[-1] for line in symbols.splitlines() if len(line.split()) >= 3 and line.split()[-2] in ('T','D','B','R')}
        require(imports <= {'memcpy','memset','memcmp','memmove','strcmp','strncmp','strlen','strchr','snprintf','risc_runtime_get_api','malloc','free','calloc'}, 'Private provider imports')
        require(exports_found == {'t5_driver_get'}, 'Unexpected provider exports')
        results.append({'command': command, 'elf': record(elf.read_bytes()), 'compaction': compaction, 'imports': sorted(imports)})
    first = (output/'a/driver.elf').read_bytes(); second = (output/'b/driver.elf').read_bytes()
    require(first == second, 'Power provider independent builds differ')
    manifest = (product/'drivers/power_axp2101/manifest.json').read_bytes()
    proof = {'schema':1, 'independent_builds_identical':True, 'target_instructions_executed':False,
        'hardware_tested':False, 'source':record((product/'drivers/power_axp2101/driver.c').read_bytes()),
        'manifest':record(manifest), 'compiler':record(compiler.resolve().read_bytes()), 'headers':headers, 'builds':results}
    (output/'build.json').write_text(json.dumps(proof, sort_keys=True, indent=2)+'\n')
    return first, manifest, proof
