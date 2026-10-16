#!/usr/bin/env python3
"""Assemble, admit and package the native catalog fix over exact .41, offline.
No publication, device I/O, formatting or migration. Never use Python -O.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / 'docs/t063-catalog-acquire'
PINS = json.loads((DOCS / 'source-pins.json').read_text())
PRODUCT = 'michaelrolphone-cmyk/RiscRTE-Wavshare-S3-Touch-AMOLED-2.06'
PREFIX = 'Waveshare-0.1.43-Catalog-Acquire'
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
    'scripts/package_catalog_acquire.py', 'scripts/test_catalog_acquire_release.py',
    'scripts/verify_t051_admission.py', 'scripts/stage_vendor_display.py',
    'native/VendorDisplay.cpp', '.github/workflows/catalog-acquire-release.yml',
    'docs/t063-catalog-acquire/source-pins.json',
    'docs/t063-catalog-acquire/RELEASE-NOTES.txt',
    'docs/t063-catalog-acquire/PRESERVING-UPDATE.txt',
    'docs/t063-catalog-acquire/prepare.py',
    'docs/t063-catalog-acquire/verify_readbacks.py',
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
    require(len(data) == 0x1000000 and sha(data) == PINS['baseline_sha256'], 'Exact released .41 factory required')

def verify_native_identity(native):
    firmware = native['firmware.bin']
    require(24 <= len(firmware) <= 0x260000, 'Invalid native firmware size')
    require(firmware[2:4] == bytes.fromhex('024f'), 'Expected DIO/80MHz/16MiB native image')
    for name in ('firmware.bin', 'firmware.elf'):
        require(set(re.findall(rb'RTE_SOURCE=([^\x00\s]+)', native[name])) == {PINS['runtime_revision'].encode()}, 'Compiled Runtime source mismatch')
        for marker in ('RISC_PAIRED_STORE_ABI:3', 'RISC_APP_POLICY_ROWS:32', 'RISC_APP_REQUIREMENT_ROWS:32', 'esp32s3-16mb-waveshare-expanded'):
            require(marker.encode() + b'\0' in native[name], 'Native profile marker absent: ' + marker)

def verify_sources(runtime, image_helper, vendor):
    require(re.fullmatch('[0-9a-f]{40}', PINS['runtime_revision']), 'Final Runtime fix commit required')
    for path, revision in ((runtime, PINS['runtime_revision']), (image_helper, PINS['image_helper_revision']), (vendor, PINS['vendor_revision'])):
        require(run('git', '-C', path, 'rev-parse', 'HEAD').strip() == revision, 'Pinned source HEAD mismatch')
        require(not run('git', '-C', path, 'status', '--porcelain', '--untracked-files=no').strip(), 'Tracked source is dirty')
    # A release must carry a source-owned native build, including retained .41 inputs.
    hashes = {}
    for name in ('expanded-candidate.ini', 'waveshare-settings-profile.h', 'partitions-paired-appdata-expanded.csv', 'scripts/reproducible_build.py'):
        data = (runtime / name).read_bytes()
        require(data == git_bytes(runtime, PINS['baseline_runtime'], name), 'Unrelated native profile change: ' + name)
        hashes[name] = sha(data)
    for name in ('native/VendorDisplay.cpp', 'scripts/stage_vendor_display.py'):
        data = (ROOT / name).read_bytes()
        require(data == git_bytes(ROOT, PINS['baseline_product'], name), 'Vendor staging differs from .41')
        hashes['product/' + name] = sha(data)
    require((runtime / 'src/VendorDisplay.cpp').read_bytes() == (ROOT / 'native/VendorDisplay.cpp').read_bytes(), 'Staged vendor backend mismatch')
    # Staging is deterministic; these are the only additional native sources.
    extra = run('git', '-C', runtime, 'ls-files', '--others', '--exclude-standard').splitlines()
    require(all(name == 'src/VendorDisplay.cpp' or name.startswith('lib/WaveshareVendorGfx/') for name in extra), 'Unexpected untracked Runtime source')
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
    for name in ('baseline', 'runtime', 'native', 'image-helper', 'vendor', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--source-revision', required=True)
    args = parser.parse_args()
    require(__debug__, 'Do not run with Python -O')
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
    require(original['version'] == '0.1.41' and original['source_revision'] == PINS['baseline_product'], 'Baseline cohort identity mismatch')
    require(sha(before['springboard.elf']) == PINS['springboard_sha256'], 'Baseline diagnostic Springboard mismatch')
    native = {name: (native_dir / name).read_bytes() for name in ('firmware.bin', 'firmware.elf', 'bootloader.bin', 'partitions.bin')}
    firmware = native['firmware.bin']
    require(firmware != old_native and 0 < len(firmware) <= 0x260000, 'Fresh bounded native firmware required')
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
    proof['radio_iq'] = prove(native['firmware.elf'], target_identity='esp32s3-16mb-waveshare-expanded')
    # Do not replace shipped bootloader or partition table on a native update.
    require(native['partitions.bin'] == baseline[0x8000:0x8000 + len(native['partitions.bin'])], 'Native partition layout differs from installed .41')
    proof.update(runtime_revision=PINS['runtime_revision'], bin_sha256=sha(firmware), elf_sha256=sha(native['firmware.elf']), elf_bin_identical=True, source_hashes=source_hashes)
    store = dict(before)
    cohort = dict(original, version=PINS['version'], source_revision=args.source_revision, runtime_version=version[0].decode(), firmware_size=len(firmware), firmware_sha256=sha(firmware))
    store['cohort.json'] = (json.dumps(cohort, separators=(',', ':')) + '\n').encode()
    require(sorted(k for k in store if store[k] != before[k]) == ['cohort.json'], 'Only cohort metadata may change in store')
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
    metadata = dict(PINS, source_revision=args.source_revision, candidate_sha256=sha(candidate), native_sha256=sha(firmware), native_elf_sha256=sha(native['firmware.elf']), hardware_tested=False, device_accessed=False, verified_hardware_fix=False, system_unchanged=True, all_store_payloads_unchanged=True, includes_t023_provisioning=False, factory_erases_saved_data=True, sd_unchanged=True)
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
    with tempfile.TemporaryDirectory(prefix='catalog-acquire-admission-') as td:
        temporary = Path(td)
        for label, files in (('baseline', before), ('candidate', store)):
            for name, data in files.items():
                path = temporary / label / name; path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(data)
        run(sys.executable, ROOT / 'scripts/verify_t051_admission.py', '--runtime', runtime, '--watch', image_helper, '--baseline-store', temporary / 'baseline', '--store', temporary / 'candidate', '--output', temporary / 'admission')
        admission = json.loads((temporary / 'admission/admission.json').read_text())
        require(admission['result']['prepared'] and admission['result']['cohort_validated'] and admission['result']['elf_count'] == 62, 'Full 62-ELF source-bound admission failed')
        require(admission['result']['hardware_calls'] == 0 and admission['result']['storage_calls'] == 0, 'Admission invoked native I/O')
        require(admission['result']['native_elf_sha256'] == sha(native['firmware.elf']), 'Admission used different native ELF')
        run(sys.executable, ROOT / 'scripts/verify_t051_admission.py', '--runtime', runtime, '--watch', image_helper, '--baseline-store', temporary / 'baseline', '--store', temporary / 'candidate', '--output', temporary / 'admission-sanitized', env={**os.environ, 'SANITIZE': '1'})
        sanitized = json.loads((temporary / 'admission-sanitized/admission.json').read_text())
        require(sanitized['result'] == admission['result'], 'Sanitized admission result differs')
        kit = dict(helpers, **{'baseline.bin': baseline, 'candidate.bin': candidate, 'release.json': encoded(metadata), 'prepare.py': (DOCS / 'prepare.py').read_bytes(), 'verify_readbacks.py': (DOCS / 'verify_readbacks.py').read_bytes(), 'README.txt': (DOCS / 'PRESERVING-UPDATE.txt').read_bytes()})
        kit_dir = temporary / 'kit'; kit_dir.mkdir()
        for name, data in kit.items():
            (kit_dir / name).write_bytes(data)
        run(sys.executable, kit_dir / 'prepare.py', '--snapshot', kit_dir / 'baseline.bin', '--output', temporary / 'plan')
        for flags in ([], ['--selection']):
            run(sys.executable, kit_dir / 'verify_readbacks.py', '--plan', temporary / 'plan/plan.json', '--readbacks', temporary / 'plan', *flags)
    report = dict(metadata, packing=packing, changed_store_files=['cohort.json'], store_file_count=len(store), native_proof=proof, preserving_banks=results, kit_prepare_and_simulated_readbacks=True)
    notes = (DOCS / 'RELEASE-NOTES.txt').read_text() + f'\nProduct source: https://github.com/{PRODUCT}/commit/{args.source_revision}\nRuntime source: https://github.com/michaelrolphone-cmyk/RiscRTE/commit/{PINS["runtime_revision"]}\nFactory SHA-256: {sha(candidate)}\nNative SHA-256: {sha(firmware)}\n'
    evidence = {'release.json': encoded(metadata), 'assembly-report.json': encoded(report), 'admission.json': encoded(admission), 'admission-sanitized.json': encoded(sanitized), 'native-proof.json': encoded(proof), 'store-SHA256SUMS.txt': checksums(store), 'firmware.elf': native['firmware.elf'], 'firmware.bin': firmware, 'README.txt': notes.encode()}
    for name in ('package_catalog_acquire.py', 'test_catalog_acquire_release.py', 'verify_t051_admission.py', 'stage_vendor_display.py'):
        evidence['product-sources/' + name] = (ROOT / 'scripts' / name).read_bytes()
    evidence['product-sources/VendorDisplay.cpp'] = (ROOT / 'native/VendorDisplay.cpp').read_bytes()
    evidence['product-sources/catalog-acquire-release.yml'] = (ROOT / '.github/workflows/catalog-acquire-release.yml').read_bytes()
    evidence['source-pins.json'] = encoded(PINS)
    evidence['runtime-source-diff.patch'] = subprocess.check_output(['git', '-C', str(runtime), 'diff', PINS['baseline_runtime'], PINS['runtime_revision']])
    for name in ('src/bootstrap/Runtime.h', 'test/run_app_capability_dispatch_tags_test.sh', 'test/run_app_catalog_runtime_test.sh', 'test/run_atomic_key_value_runtime_test.sh', 'docs/APP_CATALOG_ATOMIC_DISPATCH.md'):
        evidence['runtime-sources/' + name] = (runtime / name).read_bytes()
    for name, data in helpers.items():
        evidence['runtime-sources/' + name] = data
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / FACTORY).write_bytes(candidate)
    (args.output / 'release.json').write_bytes(encoded(metadata))
    (args.output / 'RELEASE-NOTES.txt').write_text(notes)
    archive(args.output / (PREFIX + '-preserving-kit-from-0.1.41.zip'), kit)
    archive(args.output / (PREFIX + '-evidence.zip'), evidence)
    files = {path.name: path.read_bytes() for path in args.output.iterdir() if path.is_file()}
    (args.output / 'SHA256SUMS.txt').write_bytes(checksums(files))
    print(json.dumps(dict(output=str(args.output), **metadata), indent=2))

if __name__ == '__main__':
    main()
