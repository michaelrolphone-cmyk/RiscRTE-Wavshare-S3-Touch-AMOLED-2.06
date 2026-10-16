#!/usr/bin/env python3
"""Assemble, validate and package native-resolution Springboard release outputs over exact .43, offline.
Prepare source-bound release artifacts and preserving-update proofs. Never use Python -O.
"""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import tarfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / 'docs/t030-native-ui'
PINS = json.loads((DOCS / 'source-pins.json').read_text())
PRODUCT = 'michaelrolphone-cmyk/RiscRTE-Wavshare-S3-Touch-AMOLED-2.06'
PREFIX = 'Waveshare-0.1.44-Native-UI'
FACTORY = PREFIX + '-factory-erases-data-0x0.bin'
RUNTIME_HELPERS = ('prepare_preserving_update.py', 'paired_bank_images.py', 'spiffs_image.py')

def require(ok, message):
    if not ok:
        raise ValueError(message)

def sha(data):
    return hashlib.sha256(data).hexdigest()

def encoded(value):
    return (json.dumps(value, indent=2, sort_keys=True) + '\n').encode()

def run(*args, **kwargs):
    try:
        return subprocess.run([str(arg) for arg in args], check=True, capture_output=True, text=True, **kwargs).stdout
    except subprocess.CalledProcessError as error:
        print(error.stdout, file=sys.stderr)
        print(error.stderr, file=sys.stderr)
        raise

def git_bytes(repo, revision, name):
    return subprocess.check_output(['git', '-C', str(repo), 'show', revision + ':' + name])

def checksums(files):
    return ''.join(f'{sha(data)}  {name}\n' for name, data in sorted(files.items())).encode()

def archive(path, files):
    files = dict(files)
    files['SHA256SUMS.txt'] = checksums(files)
    with zipfile.ZipFile(path, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as target:
        for name, data in sorted(files.items()):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            target.writestr(info, data, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    with zipfile.ZipFile(path) as result:
        require(result.testzip() is None, 'ZIP CRC failed')
        require(set(result.namelist()) == set(files), 'ZIP member set changed')
        for name, data in files.items():
            require(result.read(name) == data, 'ZIP member changed: ' + name)

PRODUCT_INPUTS = (
    'scripts/package_native_ui.py', 'scripts/test_native_ui_release.py',
    'scripts/home_retained_wake_policy.py', 'tests/test_home_retained_wake_policy.py',
    'scripts/build_native_ui_target.py', 'scripts/qualify_native_ui_sources.py', 'scripts/native_ui_profile.py', 'scripts/verify_native_ui_admission.py',
    'docs/catalog-display-custody/target-command.json',
    'scripts/verify_t051_admission.py', 'scripts/stage_vendor_display.py',
    'native/VendorDisplay.cpp', 'tests/test_vendor_native.py', 'tests/test_vendor_timing.py',
    'docs/NATIVE_DISPLAY_TIMING.md', 'scripts/decode_display_perf.py',
    'tests/test_display_perf_decoder.py', '.github/workflows/native-ui-release.yml',
    'docs/t030-native-ui/source-pins.json',
    'docs/t030-native-ui/RELEASE-NOTES.txt',
    'docs/t030-native-ui/PRESERVING-UPDATE.txt',
    'docs/t030-native-ui/RELEASE-ROUTE.txt',
    'docs/t030-native-ui/prepare.py',
    'docs/t030-native-ui/verify_readbacks.py',
)

def verify_product_source(root, revision, names=PRODUCT_INPUTS):
    require(re.fullmatch('[0-9a-f]{40}', revision), 'Full product commit SHA required')
    require(run('git', '-C', root, 'rev-parse', 'HEAD').strip() == revision, 'Product source identity mismatch')
    require(not run('git', '-C', root, 'diff', 'HEAD', '--name-only').strip(), 'Product sources are dirty')
    hashes = {}
    for name in names:
        data = (root / name).read_bytes()
        require(data == git_bytes(root, revision, name), 'Release input is not source-owned: ' + name)
        hashes[name] = sha(data)
    return hashes

def verify_baseline_bytes(data):
    require(len(data) == 0x1000000 and sha(data) == PINS['baseline_sha256'], 'Exact released .43 factory required')

def verify_final_pins():
    require(type(PINS.get('publication_enabled')) is bool, 'Explicit publication gate required')
    require(PINS.get('finalized') is True, 'Release source pins are not finalized; STOP')
    require((PINS.get('version'), PINS.get('baseline_version'), PINS.get('release_tag')) ==
            ('0.1.44', '0.1.43', 'test-native-ui-0.1.44'), 'Release identity differs from this source-owned route')
    require(PINS.get('performance_trace_capacity') == 64, 'Qualified native trace capacity must be 64')
    require(PINS.get('remove_springboard_flags') == [] and PINS.get('add_springboard_flags') == ['-DPORTABLE_STAGE_PROFILE'], 'Qualified app flags must retain all features and add bounded profiling only')
    for key in ('runtime_revision', 'system_revision', 'bridge_revision', 'image_helper_revision', 'vendor_revision'):
        require(isinstance(PINS.get(key), str) and re.fullmatch('[0-9a-f]{40}', PINS[key]), 'Final immutable source pin required: ' + key)
    require(PINS.get('native_changed') is True, 'Traced .44 native firmware must be explicitly changed')
    require(isinstance(PINS.get('springboard_manifest_version'), str) and re.fullmatch(r'\d+\.\d+\.\d+', PINS['springboard_manifest_version']), 'Final Springboard manifest version required')
    require(PINS['changed_store_files'] == ['boot.json', 'cohort.json', 'default.json', 'springboard.elf', 'springboard.json'], 'Additional component change requires a source-owned builder and guards')
    require(set(PINS['changed_product_native_inputs']) <= {'native/VendorDisplay.cpp', 'scripts/stage_vendor_display.py'}, 'Unrecognized native product input')
    require(PINS['native_changed'] or (PINS['runtime_revision'] == PINS['baseline_runtime'] and not PINS['changed_product_native_inputs']), 'Native unchanged requires exact baseline native inputs')

def provision_home_store(before):
    from home_retained_wake_policy import provision
    require(sha(before['default.elf']) == PINS['baseline_home_sha256'], 'Shipped Home ELF identity mismatch')
    manifest, boot = json.loads(before['default.json']), json.loads(before['boot.json'])
    rows = boot.get('app_capabilities', [])
    matches = [i for i, row in enumerate(rows) if row.get('manifest') == 'default.json']
    require(len(matches) == 1, 'Expected one exact Home boot policy')
    manifest, rows[matches[0]] = provision(manifest, rows[matches[0]])
    store = dict(before)
    for name, value in (('default.json', manifest), ('boot.json', boot)):
        store[name] = (json.dumps(value, separators=(',', ':')) + '\n').encode()
    return store

def replace_springboard(before, springboard):
    require(springboard != before['springboard.elf'], 'New Springboard must differ from baseline')
    require(springboard[:7] == b'\x7fELF\x01\x01\x01' and springboard[16:20] == b'\x03\x00\x5e\x00', 'Expected ELF32 Xtensa ET_DYN Springboard')
    manifest = json.loads(before['springboard.json'])
    require(manifest['version'] != PINS['springboard_manifest_version'], 'Springboard version must change')
    store = provision_home_store(before)
    store['springboard.elf'] = springboard
    store['springboard.json'] = (json.dumps(dict(manifest, version=PINS['springboard_manifest_version']), separators=(',', ':')) + '\n').encode()
    return store

def verify_changed_store(before, store):
    require(set(before) == set(store), 'Store member set changed')
    changed = sorted(name for name in store if store[name] != before[name])
    require(changed == PINS['changed_store_files'], 'Unapproved store changes: ' + str(changed))
    require(sum(name.endswith('.elf') for name in store) == 62, 'Complete 62-ELF baseline required')
    expected_manifest = dict(json.loads(before['springboard.json']), version=PINS['springboard_manifest_version'])
    require(json.loads(store['springboard.json']) == expected_manifest, 'Unexpected Springboard manifest changes')
    expected_home = provision_home_store(before)
    require(all(store[name] == expected_home[name] for name in ('default.json', 'boot.json')), 'Unexpected retained-wake policy changes')
    require(store['default.elf'] == before['default.elf'], 'Home ELF changed')
    return changed

def verify_font_custody(system):
    prefix = 'lib/PortableApps/fonts/'
    retained = ('SOURCES.json', 'icons.inc', 'text.inc', 'LICENSE-Orbitron.txt',
                'LICENSE-Rajdhani.txt', 'LICENSE-FontAwesome.txt')
    input_names = ('fa-solid-900.woff2', 'fa-regular-400.woff2', 'Orbitron-500.ttf', 'Rajdhani-600.ttf')
    names = [prefix + name for name in (*retained, 'native_vectors.inc', 'native_vectors_sources.json')]
    names += [prefix + 'native_sources/' + name for name in input_names]
    names += ['scripts/generate_springboard_native_vectors.py', 'lib/PortableApps/src/nova_vector.inc',
              'lib/PortableApps/src/nova_native.inc', 'lib/PortableApps/src/nova.inc']
    files = {name: (system / name).read_bytes() for name in names}
    for name, data in files.items():
        require(data == git_bytes(system, PINS['system_revision'], name), 'Font/raster input is not source-owned: ' + name)
    for name in retained:
        require(files[prefix + name] == git_bytes(system, PINS['baseline_system'], prefix + name), 'Retained font or license changed: ' + name)
    original = json.loads(files[prefix + 'SOURCES.json'])
    native = json.loads(files[prefix + 'native_vectors_sources.json'])
    require(native['source_sha256'] == sha(files[prefix + 'native_vectors.inc']), 'Native vector output hash mismatch')
    require(set(native['sources']) == set(input_names), 'Unexpected vector font inputs')
    for name, digest in native['sources'].items():
        data = files[prefix + 'native_sources/' + name]
        require(sha(data) == digest, 'Vector font input hash mismatch: ' + name)
        if name.endswith('.ttf'):
            require(digest == original['files'][name], 'Text font differs from licensed baseline font')
        else:
            blob = hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()
            expected = {'fa-solid-900.woff2': '0097ffd06bdd71a60679ad9474bfa97e1e90201f',
                        'fa-regular-400.woff2': 'e7c86422b686a8a304869355070e127eac2ad2b2'}[name]
            require(blob == expected, 'Font Awesome source blob mismatch: ' + name)
    require(native['fontawesome_commit'] == original['fontawesome_commit'], 'Font Awesome source commit mismatch')
    require(native['text_source_repository'] == 'michaelrolphone-cmyk/RiscRTE-Watch'
            and native['text_source_commit'] == PINS['bridge_revision']
            and native['text_source_path'] == 'apps/clock/nova/fonts', 'Text source location changed')
    generator = native['generator']
    require(generator['fonttools'] == '4.61.1' and generator['python'] == '3.12.14'
            and generator['brotli']['version'] == '1.1.0'
            and generator['brotli']['implementation'] in ('libbrotlidec', 'python-brotli'),
            'Unpinned vector generator versions')
    require(native['glyphs'] == 168 and native['encoding'] == 'delta-varint vector commands; LZSS4096/18',
            'Native vector inventory or encoding differs from qualified renderer')
    return files, dict(source_sha256={name: sha(data) for name, data in files.items()},
                       original_font_inputs_retained=True, license_texts_retained=True,
                       native_vector_provenance=native)


def verify_native_identity(native):
    firmware = native['firmware.bin']
    require(24 <= len(firmware) <= 0x260000, 'Invalid native firmware size')
    require(firmware[2:4] == bytes.fromhex('024f'), 'Expected DIO/80MHz/16MiB native image')
    for name in ('firmware.bin', 'firmware.elf'):
        require(set(re.findall(rb'RTE_SOURCE=([^\x00\s]+)', native[name])) == {PINS['runtime_revision'].encode()}, 'Compiled Runtime source mismatch')
        for marker in ('RISC_PAIRED_STORE_ABI:3', 'RISC_APP_POLICY_ROWS:32', 'RISC_APP_REQUIREMENT_ROWS:32', 'esp32s3-16mb-waveshare-expanded', 'RISCRTE_VENDOR_DISPLAY_TIMING_V1'):
            require(marker.encode() + b'\0' in native[name], 'Native profile marker absent: ' + marker)

def verify_trace_storage(data):
    from elftools.elf.elffile import ELFFile
    image = ELFFile(io.BytesIO(data))
    objects = {symbol.name: symbol['st_size'] for symbol in image.get_section_by_name('.symtab').iter_symbols()
               if symbol['st_info']['type'] == 'STT_OBJECT' and symbol['st_shndx'] != 'SHN_UNDEF'}
    require(objects.get('_ZN8RiscPerf4dataE') == 0xd40, 'Native recorder is not the qualified 64-record/64-counter layout')
    replay = {name: size for name, size in objects.items() if 'performanceReplay' in name}
    require(len(replay) == 1 and next(iter(replay.values())) == 0xe58, 'Native replay snapshot is not the qualified bounded layout')
    return dict(history_records=64, cumulative_phase_counters=64, recorder_bytes=0xd40,
                replay_bytes=0xe58, replay_symbol=next(iter(replay)), native_symbol_sizes_verified=True)

def verify_vendor_tree(vendor, revision):
    prefix = 'examples/arduino/libraries/Arduino_GFX'
    archive_bytes = subprocess.check_output(['git', '-C', str(vendor), 'archive', revision, '--', prefix])
    with tarfile.open(fileobj=io.BytesIO(archive_bytes)) as archive:
        require(all(row.isfile() or row.isdir() for row in archive), 'Unsupported vendor source entry')
        expected = {row.name.removeprefix(prefix + '/'): archive.extractfile(row).read()
                    for row in archive if row.isfile()}
        require(all(row.name.startswith(prefix + '/') for row in archive if row.isfile()), 'Unexpected vendor archive path')
    root = vendor / prefix
    paths = list(root.rglob('*'))
    require(not any(path.is_symlink() for path in paths), 'Vendor source symlink is not permitted')
    actual = {path.relative_to(root).as_posix(): path.read_bytes() for path in paths if path.is_file()}
    require(actual == expected, 'Vendor source tree differs from exact Git archive (including untracked/ignored files)')
    return sha(archive_bytes)


def verify_sources(runtime, image_helper, vendor):
    verify_final_pins()
    for path, revision in ((runtime, PINS['runtime_revision']), (image_helper, PINS['image_helper_revision']), (vendor, PINS['vendor_revision'])):
        require(run('git', '-C', path, 'rev-parse', 'HEAD').strip() == revision, 'Pinned source HEAD mismatch')
        require(not run('git', '-C', path, 'status', '--porcelain', '--untracked-files=no').strip(), 'Tracked source is dirty')
    # A release must carry a source-owned native build, including retained .43 inputs.
    hashes = {'vendor-upstream-archive': verify_vendor_tree(vendor, PINS['vendor_revision'])}
    for name in ('expanded-candidate.ini', 'waveshare-settings-profile.h', 'partitions-paired-appdata-expanded.csv', 'scripts/reproducible_build.py'):
        data = (runtime / name).read_bytes()
        require(data == git_bytes(runtime, PINS['baseline_runtime'], name), 'Unrelated native profile change: ' + name)
        hashes[name] = sha(data)
    for name in ('native/VendorDisplay.cpp', 'scripts/stage_vendor_display.py'):
        data = (ROOT / name).read_bytes()
        if name not in PINS['changed_product_native_inputs']:
            require(data == git_bytes(ROOT, PINS['baseline_product'], name), 'Unapproved native product change: ' + name)
        hashes['product/' + name] = sha(data)
    require((runtime / 'src/VendorDisplay.cpp').read_bytes() == (ROOT / 'native/VendorDisplay.cpp').read_bytes(), 'Staged vendor backend mismatch')
    # Staging is deterministic; these are the only additional native sources.
    from native_ui_profile import PROFILE_NAME, verify_profile
    hashes[PROFILE_NAME] = verify_profile(runtime)
    extra = run('git', '-C', runtime, 'ls-files', '--others', '--exclude-standard').splitlines()
    require(all(name in ('src/VendorDisplay.cpp', PROFILE_NAME) or name.startswith('lib/WaveshareVendorGfx/') for name in extra), 'Unexpected untracked Runtime source')
    # Independently regenerate vendor staging from exact upstream source.
    with tempfile.TemporaryDirectory(prefix='catalog-vendor-custody-') as td:
        staging = Path(td)
        for name in ('native/VendorDisplay.cpp', 'scripts/stage_vendor_display.py'):
            target = staging / 'product' / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes((ROOT / name).read_bytes())
        (staging / 'runtime/src').mkdir(parents=True)
        run(sys.executable, staging / 'product/scripts/stage_vendor_display.py', '--vendor', vendor, '--runtime', staging / 'runtime')
        expected = {p.relative_to(staging / 'runtime').as_posix(): p.read_bytes()
                    for p in (staging / 'runtime').rglob('*') if p.is_file()}
        actual = {p.relative_to(runtime).as_posix(): p.read_bytes()
                  for p in (runtime / 'lib/WaveshareVendorGfx').rglob('*') if p.is_file()}
        actual['src/VendorDisplay.cpp'] = (runtime / 'src/VendorDisplay.cpp').read_bytes()
        require(actual == expected, 'Staged vendor library differs from exact pinned recipe')
    hashes.update({name: sha((runtime / name).read_bytes()) for name in extra})
    hashes['platformio.ini'] = sha((runtime / 'platformio.ini').read_bytes())
    return hashes

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('baseline', 'runtime', 'native', 'system', 'bridges', 'compiler', 'image-helper', 'vendor', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--source-revision', required=True)
    parser.add_argument('--font-python', default=sys.executable)
    args = parser.parse_args()
    require(__debug__, 'Do not run with Python -O')
    verify_final_pins()
    product_source_hashes = verify_product_source(ROOT, args.source_revision)
    require(not args.output.exists() or not any(args.output.iterdir()), 'Output must be empty')
    runtime, image_helper, native_dir = args.runtime.resolve(), args.image_helper.resolve(), args.native.resolve()
    require(native_dir == runtime / '.pio/build/waveshare-t051', 'Native output must be selected waveshare-t051 build')
    source_hashes = verify_sources(runtime, image_helper, args.vendor.resolve())
    source_hashes.update({'product/' + name: digest for name, digest in product_source_hashes.items()})
    sys.path[:0] = [str(runtime / 'scripts'), str(image_helper / 'scripts')]
    from prepare_preserving_update import layout, pair, plan, record, selection, ota
    from spiffs_image import read_image
    from paired_bank_images import initial_bank_state
    from paired_candidate import native_proof
    from radio_iq_proof import prove
    from release_assets import esp_image, elf
    import current_bootfs

    baseline = args.baseline.read_bytes()
    verify_baseline_bytes(baseline)
    geometry = layout(baseline)
    require(geometry[0] and geometry[3] == 0x550000, 'ABI3 expanded geometry required')
    _, old_native, old_store = pair(baseline, 0, geometry)
    before = read_image(old_store, geometry[3])
    original = json.loads(before['cohort.json'])
    require(original['version'] == '0.1.43' and original['source_revision'] == PINS['baseline_product'], 'Baseline cohort identity mismatch')
    require(sha(before['springboard.elf']) == PINS['baseline_springboard_sha256'], 'Baseline diagnostic Springboard mismatch')
    native = {name: (native_dir / name).read_bytes() for name in ('firmware.bin', 'firmware.elf', 'bootloader.bin', 'partitions.bin')}
    firmware = native['firmware.bin']
    require(0 < len(firmware) <= 0x260000, 'Bounded native firmware required')
    require((firmware != old_native) == PINS['native_changed'], 'Native changed status differs from finalized pins')
    require(sha(old_native) == PINS['baseline_native_sha256'], 'Baseline native hash mismatch')
    esp_image(firmware)
    elf(native['firmware.elf'])
    verify_native_identity(native)
    # Regenerate image from this exact ELF, proving ELF/BIN correspondence.
    with tempfile.TemporaryDirectory(prefix='catalog-native-proof-') as td:
        regenerated = Path(td) / 'firmware.bin'
        run(sys.executable, '-m', 'esptool', '--chip', 'esp32s3', 'elf2image', '--flash_mode', 'dio', '--flash_freq', '80m', '--flash_size', '16MB', '-o', regenerated, native_dir / 'firmware.elf')
        require(regenerated.read_bytes() == firmware, 'Native BIN does not match supplied ELF')
    version = re.findall(rb'RISC_RUNTIME_VERSION:([^\x00]+)', firmware)
    require(len(version) == 1, 'Ambiguous Runtime version')
    proof = native_proof(native['firmware.elf'])
    proof['performance_trace'] = verify_trace_storage(native['firmware.elf'])
    proof['radio_iq'] = prove(native['firmware.elf'], target_identity='esp32s3-16mb-waveshare-expanded')
    proof['performance_trace']['static_bytes_before_iq_bank'] = proof['radio_iq']['bank_base'] - proof['radio_iq']['heap_start']
    # Do not replace shipped bootloader or partition table on a native update.
    require(native['partitions.bin'] == baseline[0x8000:0x8000 + len(native['partitions.bin'])], 'Native partition layout differs from installed .43')
    proof.update(runtime_revision=PINS['runtime_revision'], bin_sha256=sha(firmware), elf_sha256=sha(native['firmware.elf']), elf_bin_identical=True, source_hashes=source_hashes)
    with tempfile.TemporaryDirectory(prefix='native-ui-target-') as td:
        target = Path(td) / 'target'
        run(sys.executable, ROOT / 'scripts/build_native_ui_target.py', '--system', args.system.resolve(), '--bridges', args.bridges.resolve(), '--compiler', args.compiler.resolve(), '--font-python', args.font_python, '--output', target)
        target_proof = json.loads((target / 'target-proof.json').read_text())
        springboard = (target / 'candidate/springboard.elf').read_bytes()
        springboard_debug = (target / 'candidate/springboard.debug.elf').read_bytes()
        require(target_proof['results'][0]['sha256'] == PINS['baseline_springboard_sha256'], 'Shipped Springboard did not reproduce')
        require(target_proof['results'][1]['sha256'] == sha(springboard), 'Candidate target proof mismatch')
    with tempfile.TemporaryDirectory(prefix='native-ui-qualifications-') as td:
        qualification_dir = Path(td) / 'results'
        debug_path = Path(td) / 'springboard.debug.elf'
        debug_path.write_bytes(springboard_debug)
        run(sys.executable, ROOT / 'scripts/qualify_native_ui_sources.py', '--system', args.system.resolve(), '--bridges', args.bridges.resolve(), '--output', qualification_dir, '--target-debug-elf', debug_path, '--target-objdump', str(args.compiler.resolve()).removesuffix('gcc') + 'objdump')
        source_qualification = json.loads((qualification_dir / 'qualification.json').read_text())
        require(source_qualification['product_revision'] == args.source_revision, 'Cadence used a different product provider revision')
        qualification_files = {p.relative_to(qualification_dir).as_posix(): p.read_bytes()
                               for p in qualification_dir.rglob('*') if p.is_file() and p.suffix in ('.json', '.log')}
    font_sources, font_proof = verify_font_custody(args.system.resolve())
    store = replace_springboard(before, springboard)
    cohort = dict(original, version=PINS['version'], source_revision=args.source_revision, runtime_version=version[0].decode(), firmware_size=len(firmware), firmware_sha256=sha(firmware))
    store['cohort.json'] = (json.dumps(cohort, separators=(',', ':')) + '\n').encode()
    changed_store = verify_changed_store(before, store)
    packed, packing = current_bootfs.build(store, size=geometry[3])
    require(read_image(packed, geometry[3]) == store, 'Packed store round-trip differs')
    candidate = bytearray(baseline)
    candidate[0x10000:0x270000] = b'\xff' * 0x260000
    candidate[0x10000:0x10000 + len(firmware)] = firmware
    candidate[0x2f0000:0x840000] = packed
    state = initial_bank_state(firmware, packed, True, True)
    candidate[0xff2000:0xff2000 + len(state)] = state
    candidate = bytes(candidate)
    require(layout(candidate) == geometry and pair(candidate, 0, geometry)[1:] == (firmware, packed), 'Candidate bank binding failed')
    for start, end in ((0, 0x10000), (0x270000, 0x2f0000), (0x840000, 0xff2000), (0xff3000, 0x1000000)):
        require(candidate[start:end] == baseline[start:end], 'Bytes outside native/store/state changed')
    helpers = {name: (runtime / 'scripts' / name).read_bytes() for name in RUNTIME_HELPERS}
    require(all(data == git_bytes(runtime, PINS['runtime_revision'], 'scripts/' + name) for name, data in helpers.items()), 'Preserving helper source mismatch')
    metadata = dict(PINS, source_revision=args.source_revision, candidate_sha256=sha(candidate), native_sha256=sha(firmware), native_elf_sha256=sha(native['firmware.elf']), hardware_tested=False, device_accessed=False, verified_hardware_fix=False, system_unchanged=False, native_changed=PINS['native_changed'], all_other_store_payloads_unchanged=True, springboard_sha256=sha(springboard), springboard_manifest_sha256=sha(store['springboard.json']), home_elf_sha256=sha(store['default.elf']), retained_wake_policy_added=True, includes_t023_provisioning=False, factory_erases_saved_data=True, sd_unchanged=True)
    results = []
    def active(image):
        return (max(ota(image[0xff0000 + i * 4096:0xff0020 + i * 4096])[0] for i in range(2) if ota(image[0xff0000 + i * 4096:0xff0020 + i * 4096])) - 1) % 2
    for source in (0, 1):
        snapshot = bytearray(baseline)
        snapshot[0x9000:0xf000] = bytes((i * 17 + 3) % 256 for i in range(0x6000))
        snapshot[0x270000:0x2f0000] = bytes((i * 23 + 7) % 256 for i in range(0x80000))
        if source:
            snapshot[geometry[1][1]:geometry[1][1] + len(old_native)] = old_native
            snapshot[geometry[2][1]:geometry[2][1] + geometry[3]] = old_store
            snapshot[0xff3000:0xff3060] = record(1, old_native, old_store, True, True)
            snapshot[0xff1000:0xff2000] = selection(2, 2)
        writes, receipt = plan(snapshot, baseline, candidate, PINS['baseline_sha256'])
        staged = bytearray(snapshot)
        for _, offset, data in writes[:-1]:
            end = offset + (len(data) + 4095) // 4096 * 4096
            staged[offset:end] = b'\xff' * (end - offset)
            staged[offset:offset + len(data)] = data
            require(active(staged) == source, 'Active selection changed before final write')
        for start, end in receipt['preserved_ranges']:
            require(staged[start:end] == snapshot[start:end], 'Protected range changed')
        _, offset, data = writes[-1]
        for cut in range(33):
            interrupted = bytearray(staged)
            interrupted[offset:offset + 4096] = b'\xff' * 4096
            interrupted[offset:offset + cut] = data[:cut]
            require(active(interrupted) == (1 - source if cut == 32 else source), 'Interrupted selection failed')
        staged[offset:offset + len(data)] = data
        require(active(staged) == 1 - source and pair(staged, 1 - source, geometry)[1:] == (firmware, packed), 'Final native/store pair mismatch')
        for corrupt_offset in (0, 0x8000, 0x10000, 0x2f0000, 0xff2000):
            corrupt = bytearray(candidate); corrupt[corrupt_offset] ^= 1
            try:
                plan(snapshot, baseline, corrupt, PINS['baseline_sha256'])
            except ValueError:
                pass
            else:
                raise ValueError('Corrupted candidate accepted')
        for start, end in receipt['preserved_ranges']:
            require(staged[start:end] == snapshot[start:end], 'Final selection changed protected range')
        rejected = 0
        for corruption in ('bootloader', 'active-native', 'active-store', 'active-state', 'unconfirmed', 'equal-sequence'):
            invalid = bytearray(snapshot)
            if corruption == 'unconfirmed':
                selected_sector = 0xff1000 if source else 0xff0000
                invalid[selected_sector:selected_sector + 4096] = selection(source + 1, 0)
            elif corruption == 'equal-sequence':
                invalid[0xff0000:0xff1000] = selection(2, 2)
                invalid[0xff1000:0xff2000] = selection(2, 2)
            else:
                at = {'bootloader': 0, 'active-native': geometry[1][source], 'active-store': geometry[2][source], 'active-state': 0xff2000 + source * 4096}[corruption]
                invalid[at] ^= 1
            try:
                plan(invalid, baseline, candidate, PINS['baseline_sha256'])
            except ValueError:
                rejected += 1
            else:
                raise ValueError('Invalid snapshot accepted: ' + corruption)
        results.append(dict(active_bank=source, target_bank=1-source, selection_cuts=33, protected_ranges_unchanged=True, corrupt_inputs_rejected=True, invalid_snapshots_rejected=rejected))
    with tempfile.TemporaryDirectory(prefix='native-ui-admission-') as td:
        temporary = Path(td)
        for label, files in (('baseline', before), ('candidate', store)):
            for name, data in files.items():
                path = temporary / label / name; path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(data)
        run(sys.executable, ROOT / 'scripts/verify_native_ui_admission.py', '--runtime', runtime, '--watch', image_helper, '--baseline-store', temporary / 'baseline', '--store', temporary / 'candidate', '--output', temporary / 'admission')
        admission = json.loads((temporary / 'admission/admission.json').read_text())
        require(admission['result']['prepared'] and admission['result']['cohort_validated'] and admission['result']['elf_count'] == 62, 'Full 62-ELF source-bound admission failed')
        require(admission['result']['hardware_calls'] == 0 and admission['result']['storage_calls'] == 0, 'Admission invoked native I/O')
        require(admission['result']['native_elf_sha256'] == sha(native['firmware.elf']), 'Admission used different native ELF')
        run(sys.executable, ROOT / 'scripts/verify_native_ui_admission.py', '--runtime', runtime, '--watch', image_helper, '--baseline-store', temporary / 'baseline', '--store', temporary / 'candidate', '--output', temporary / 'admission-sanitized', env={**os.environ, 'SANITIZE': '1'})
        sanitized = json.loads((temporary / 'admission-sanitized/admission.json').read_text())
        require(sanitized['result'] == admission['result'], 'Sanitized admission result differs')
        kit = dict(helpers, **{'baseline.bin': baseline, 'candidate.bin': candidate, 'release.json': encoded(metadata), 'prepare.py': (DOCS / 'prepare.py').read_bytes(), 'verify_readbacks.py': (DOCS / 'verify_readbacks.py').read_bytes(), 'README.txt': (DOCS / 'PRESERVING-UPDATE.txt').read_bytes(), 'decode_display_perf.py': (ROOT / 'scripts/decode_display_perf.py').read_bytes(), 'DISPLAY-TIMING.md': (ROOT / 'docs/NATIVE_DISPLAY_TIMING.md').read_bytes()})
        kit_dir = temporary / 'kit'; kit_dir.mkdir()
        for name, data in kit.items():
            (kit_dir / name).write_bytes(data)
        run(sys.executable, kit_dir / 'prepare.py', '--snapshot', kit_dir / 'baseline.bin', '--output', temporary / 'plan')
        for flags in ([], ['--selection']):
            run(sys.executable, kit_dir / 'verify_readbacks.py', '--plan', temporary / 'plan/plan.json', '--readbacks', temporary / 'plan', *flags)
    report = dict(metadata, packing=packing, changed_store_files=changed_store, target_proof=target_proof, font_proof=font_proof, source_qualification=source_qualification, store_file_count=len(store), native_proof=proof, preserving_banks=results, kit_prepare_and_simulated_readbacks=True)
    notes = (DOCS / 'RELEASE-NOTES.txt').read_text() + f'\nProduct source: https://github.com/{PRODUCT}/commit/{args.source_revision}\nSystem source: https://github.com/michaelrolphone-cmyk/RiscRTE-System-Apps/commit/{PINS["system_revision"]}\nRuntime source: https://github.com/michaelrolphone-cmyk/RiscRTE/commit/{PINS["runtime_revision"]}\nFactory SHA-256: {sha(candidate)}\nNative SHA-256: {sha(firmware)}\n'
    evidence = {'release.json': encoded(metadata), 'assembly-report.json': encoded(report), 'admission.json': encoded(admission), 'admission-sanitized.json': encoded(sanitized), 'native-proof.json': encoded(proof), 'target-proof.json': encoded(target_proof), 'springboard.elf': springboard, 'springboard.debug.elf': springboard_debug, 'springboard.json': store['springboard.json'], 'store-SHA256SUMS.txt': checksums(store), 'firmware.elf': native['firmware.elf'], 'firmware.bin': firmware, 'README.txt': notes.encode()}
    for name in ('package_native_ui.py', 'build_native_ui_target.py', 'qualify_native_ui_sources.py', 'test_native_ui_release.py', 'native_ui_profile.py', 'verify_native_ui_admission.py', 'verify_t051_admission.py', 'stage_vendor_display.py', 'home_retained_wake_policy.py'):
        evidence['product-sources/' + name] = (ROOT / 'scripts' / name).read_bytes()
    for name in ('tests/test_vendor_native.py', 'tests/test_vendor_timing.py', 'tests/test_display_perf_decoder.py', 'tests/test_home_retained_wake_policy.py', 'scripts/decode_display_perf.py', 'docs/NATIVE_DISPLAY_TIMING.md'):
        evidence['product-sources/' + name] = (ROOT / name).read_bytes()
    evidence['product-sources/VendorDisplay.cpp'] = (ROOT / 'native/VendorDisplay.cpp').read_bytes()
    evidence['product-sources/native-ui-release.yml'] = (ROOT / '.github/workflows/native-ui-release.yml').read_bytes()
    evidence['source-pins.json'] = encoded(PINS)
    evidence['source-qualification.json'] = encoded(source_qualification)
    for name, data in qualification_files.items():
        evidence['qualification/' + name] = data
    evidence['font-proof.json'] = encoded(font_proof)
    for name in ('default.json', 'boot.json'):
        evidence['changed-store/' + name] = store[name]
    for name, data in font_sources.items():
        evidence['font-sources/' + name] = data
    evidence['system-source-diff.patch'] = subprocess.check_output(['git', '-C', str(args.system), 'diff', PINS['baseline_system'], PINS['system_revision']])
    evidence['target-command.json'] = (ROOT / 'docs/catalog-display-custody/target-command.json').read_bytes()
    evidence['runtime-source-diff.patch'] = subprocess.check_output(['git', '-C', str(runtime), 'diff', PINS['baseline_runtime'], PINS['runtime_revision']])
    for name in ('src/bootstrap/Runtime.h', 'test/run_app_capability_dispatch_tags_test.sh', 'test/run_app_catalog_runtime_test.sh', 'test/run_atomic_key_value_runtime_test.sh', 'docs/APP_CATALOG_ATOMIC_DISPATCH.md', 'src/diagnostics/Performance.h', 'test/performance_capacity_test.cpp', 'test/run_performance_capacity_test.sh', 'docs/PERFORMANCE_TRACE.md'):
        evidence['runtime-sources/' + name] = (runtime / name).read_bytes()
    for name, data in helpers.items():
        evidence['runtime-sources/' + name] = data
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / FACTORY).write_bytes(candidate)
    (args.output / 'release.json').write_bytes(encoded(metadata))
    (args.output / 'RELEASE-NOTES.txt').write_text(notes)
    (args.output / 'decode_display_perf.py').write_bytes((ROOT / 'scripts/decode_display_perf.py').read_bytes())
    (args.output / 'DISPLAY-TIMING.md').write_bytes((ROOT / 'docs/NATIVE_DISPLAY_TIMING.md').read_bytes())
    archive(args.output / (PREFIX + '-preserving-kit-from-0.1.43.zip'), kit)
    archive(args.output / (PREFIX + '-evidence.zip'), evidence)
    files = {path.name: path.read_bytes() for path in args.output.iterdir() if path.is_file()}
    (args.output / 'SHA256SUMS.txt').write_bytes(checksums(files))
    print(json.dumps(dict(output=str(args.output), **metadata), indent=2))

if __name__ == '__main__':
    main()
