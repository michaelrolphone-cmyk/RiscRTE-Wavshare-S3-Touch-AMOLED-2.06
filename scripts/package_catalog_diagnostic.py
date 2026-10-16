#!/usr/bin/env python3
"""Package the exact .39-based .41 diagnostic, offline; never publish or flash.

All archives have sorted members, fixed timestamps and level-9 deflate.
Hashes bind the exact published bytes; cross-zlib archive identity is not claimed.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / 'docs/t063-catalog-diagnostic'
VERSION = '0.1.41'
PREFIX = 'Waveshare-0.1.41-Catalog-Diagnostic'
FACTORY = PREFIX + '-factory-erases-data-0x0.bin'
BASELINE_SHA = '93531640691a0a1b3b6718e01aeca388fe3cbe6c5e4f9f396ff262d0c166fa35'
SPRINGBOARD_SHA = 'f0dd72760ece4c9102aa316281663ddd4d90eeabc54ca39f326766ce521f05a7'
RUNTIME = 'c258c4ba144247b6eaa4c6f28675ffccec582fe1'
SYSTEM = '326396614def41f4a3b11c8c193c3ac1bbb75ab0'
IMAGE_HELPER = '55f3f379b4c2ec7e18412fb2fc887d301bf6e3c0'
PRODUCT = 'michaelrolphone-cmyk/RiscRTE-Wavshare-S3-Touch-AMOLED-2.06'
RUNTIME_FILES = ('prepare_preserving_update.py', 'paired_bank_images.py', 'spiffs_image.py')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def encoded(value):
    return (json.dumps(value, indent=2, sort_keys=True) + '\n').encode()


def sums(files):
    return ''.join(f'{sha(data)}  {name}\n' for name, data in sorted(files.items())).encode()


def archive(path, files):
    files = dict(files)
    files['SHA256SUMS.txt'] = sums(files)
    with zipfile.ZipFile(path, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as target:
        for name, data in sorted(files.items()):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            target.writestr(info, data, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    with zipfile.ZipFile(path) as result:
        require(result.testzip() is None, 'ZIP CRC verification failed')
        require(set(result.namelist()) == set(files), 'ZIP member set differs')
        for name, data in files.items():
            require(result.read(name) == data, 'ZIP readback differs: ' + name)


def run(*args):
    return subprocess.run([str(arg) for arg in args], check=True, capture_output=True, text=True).stdout


def verified_runtime(runtime):
    require(run('git', '-C', runtime, 'rev-parse', 'HEAD').strip() == RUNTIME,
            'Runtime checkout is not the pinned revision')
    files = {}
    for name in RUNTIME_FILES:
        value = (runtime / 'scripts' / name).read_bytes()
        pinned = subprocess.run(['git', '-C', str(runtime), 'show',
                                 RUNTIME + ':scripts/' + name], check=True, capture_output=True).stdout
        require(value == pinned, 'Runtime helper differs from pinned source: ' + name)
        files[name] = value
    return files


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('baseline', 'candidate', 'runtime', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--source-revision', required=True, help='Exact product commit used for assembly')
    args = parser.parse_args()
    require(__debug__, 'Run without Python -O; image verification requires assertions')
    require(re.fullmatch('[0-9a-f]{40}', args.source_revision), 'Expected full product commit SHA')
    require(not args.output.exists() or not any(args.output.iterdir()), 'Output must be empty')
    runtime = args.runtime.resolve()
    helpers = verified_runtime(runtime)
    sys.path.insert(0, str(runtime / 'scripts'))
    from spiffs_image import read_image
    from prepare_preserving_update import layout, pair

    baseline = args.baseline.read_bytes()
    candidate = (args.candidate / FACTORY).read_bytes()
    require(len(baseline) == len(candidate) == 0x1000000, 'Full 16 MiB images required')
    require(sha(baseline) == BASELINE_SHA, 'Exact .39 baseline SHA mismatch')
    geometry = layout(baseline)
    require(layout(candidate) == geometry, 'Partition layout changed')
    _, original_native, original_store = pair(baseline, 0, geometry)
    _, native, packed_store = pair(candidate, 0, geometry)
    require(native == original_native, 'Native firmware changed')
    before = read_image(original_store, geometry[3])
    store = read_image(packed_store, geometry[3])
    disk_store = {path.relative_to(args.candidate / 'store').as_posix(): path.read_bytes()
                  for path in (args.candidate / 'store').rglob('*') if path.is_file()}
    require(store == disk_store, 'Candidate store directory differs from the actual BIN')
    require(set(store) == set(before), 'Store member set changed')
    changed = sorted(name for name in store if store[name] != before[name])
    require(changed == ['cohort.json', 'springboard.elf', 'springboard.json'], 'Unexpected changed store members')
    require(sha(store['springboard.elf']) == SPRINGBOARD_SHA, 'Qualified Springboard ELF SHA mismatch')
    cohort, original_cohort = json.loads(store['cohort.json']), json.loads(before['cohort.json'])
    require(original_cohort['version'] == '0.1.39', 'Unexpected source version')
    expected_cohort = dict(original_cohort, version=VERSION, source_revision=args.source_revision)
    require(cohort == expected_cohort, 'Unexpected cohort metadata changes')
    expected_manifest = dict(json.loads(before['springboard.json']), version='1.7.16')
    require(json.loads(store['springboard.json']) == expected_manifest, 'Unexpected Springboard manifest changes')
    for start, end in ((0, 0x2f0000), (0x840000, 0xff2000), (0xff3000, 0x1000000)):
        require(baseline[start:end] == candidate[start:end], 'Bytes outside the diagnostic store/state changed')
    report = json.loads((args.candidate / 'assembly-report.json').read_text())
    for key, value in {'image_sha256': sha(candidate), 'baseline_sha256': BASELINE_SHA,
                       'version': VERSION, 'baseline_version': '0.1.39',
                       'source_revision': args.source_revision, 'system_revision': SYSTEM,
                       'native_revision': RUNTIME, 'native_sha256': sha(native),
                       'springboard_sha256': SPRINGBOARD_SHA, 'diagnostic_only': True,
                       'hardware_tested': False, 'physical_root_cause_verified': False,
                       'device_accessed': False, 'native_unchanged': True,
                       'all_other_store_files_unchanged': True, 'changed_store_files': changed,
                       'factory_erases_saved_data': True, 'sd_unchanged': True}.items():
        require(report.get(key) == value, 'Assembly report mismatch: ' + key)
    proof_bytes = (DOCS / 'target-proof.json').read_bytes()
    proof = json.loads(proof_bytes)
    require(proof.get('hardware_tested') is False and proof.get('diagnostic_only') is True,
            'Target proof must retain diagnostic-only qualification')
    require([row['sha256'] for row in proof['results'] if row['profile'] == 'diagnostic'] == [SPRINGBOARD_SHA],
            'Target proof does not identify the qualified diagnostic ELF')

    metadata = {'version': VERSION, 'baseline_version': '0.1.39', 'baseline_sha256': BASELINE_SHA,
                'candidate_sha256': sha(candidate), 'springboard_sha256': SPRINGBOARD_SHA,
                'product_repository': PRODUCT, 'source_revision': args.source_revision,
                'system_revision': SYSTEM, 'runtime_revision': RUNTIME, 'image_helper_revision': IMAGE_HELPER,
                'diagnostic_only': True, 'verified_fix': False, 'hardware_tested': False,
                'device_accessed': False, 'includes_0_1_40_provisioning': False,
                'runtime_helper_sha256': {name: sha(data) for name, data in helpers.items()}}
    kit = dict(helpers, **{'baseline.bin': baseline, 'candidate.bin': candidate,
                          'release.json': encoded(metadata),
                          'prepare.py': (DOCS / 'prepare.py').read_bytes(),
                          'verify_readbacks.py': (DOCS / 'verify_readbacks.py').read_bytes(),
                          'README.txt': (DOCS / 'PRESERVING-UPDATE.txt').read_bytes()})
    with tempfile.TemporaryDirectory(prefix='catalog-release-check-') as temporary:
        temporary = Path(temporary)
        preservation_path = temporary / 'preservation-final.json'
        run(sys.executable, ROOT / 'scripts/test_catalog_diagnostic_preservation.py',
            '--runtime', runtime, '--baseline', args.baseline.resolve(),
            '--candidate', (args.candidate / FACTORY).resolve(), '--output', preservation_path)
        preservation = json.loads(preservation_path.read_text())
        require(preservation['candidate_sha256'] == sha(candidate), 'Preservation evidence has stale candidate SHA')
        require([row['active_bank'] for row in preservation['results']] == [0, 1], 'Both source banks must be tested')
        kit_dir = temporary / 'kit'
        kit_dir.mkdir()
        for name, data in kit.items():
            (kit_dir / name).write_bytes(data)
        plan_dir = temporary / 'simulated-plan'
        run(sys.executable, kit_dir / 'prepare.py', '--snapshot', kit_dir / 'baseline.bin', '--output', plan_dir)
        # These are software-generated fixtures, never hardware readbacks.
        run(sys.executable, kit_dir / 'verify_readbacks.py', '--plan', plan_dir / 'plan.json', '--readbacks', plan_dir)
        run(sys.executable, kit_dir / 'verify_readbacks.py', '--plan', plan_dir / 'plan.json', '--readbacks', plan_dir, '--selection')
        smoke = {'offline_kit_prepare': True, 'simulated_region_readbacks': True,
                 'simulated_selection_readback': True, 'hardware_tested': False, 'device_accessed': False}

    body = f'''Waveshare {VERSION} catalog diagnostic (prerelease)

Diagnostic only. This is not a verified fix for Apps unavailable and is not hardware-qualified.
It adds catalog failure stage, numeric result and index to the existing error screen.
Report those added lines or a photo after swiping Clock to Springboard.

Based only on exact 0.1.39; the separate 0.1.40 / T023 provisioning candidate is excluded.
The full 16 MiB factory BIN is flashed at offset 0 and OVERWRITES SAVED INTERNAL DATA.
For preservation, use the separate kit only with a fresh full-device readback of confirmed
exact 0.1.39. Never flash its whole baseline.bin or candidate.bin. Read PRESERVING-UPDATE
instructions in the kit: verify the three staged readbacks, then write OTA selection LAST.
Do not erase the device. The kit never accesses or flashes a device. The SD card is unchanged.

Product source: https://github.com/{PRODUCT}/commit/{args.source_revision}
System source: https://github.com/michaelrolphone-cmyk/RiscRTE-System-Apps/commit/{SYSTEM}
Runtime source (native firmware unchanged): https://github.com/michaelrolphone-cmyk/RiscRTE/commit/{RUNTIME}
Image helper: https://github.com/michaelrolphone-cmyk/RiscRTE-T-Watch-S3/commit/{IMAGE_HELPER}
Baseline release: https://github.com/{PRODUCT}/releases/tag/test-catalog-display-0.1.39
Baseline factory SHA-256: {BASELINE_SHA}
Diagnostic factory SHA-256: {sha(candidate)}
Qualified Springboard ELF SHA-256: {SPRINGBOARD_SHA}

Only springboard.elf, springboard.json, cohort.json and the matching bank-state record change.
Final-image software checks cover both source banks, preserved ranges, 33 selection cuts
per bank, corrupt input rejection and the packaged offline planner/readback-verifier flow.
The evidence ZIP contains final assembly/preservation reports, the ELF target proof,
exact packaged sources and per-member hashes. These checks do not establish a hardware fix.
Check every downloaded asset against SHA256SUMS.txt before use.
'''
    readme = body.encode() + b'\n' + (DOCS / 'README.md').read_bytes()
    evidence = {'release.json': encoded(metadata), 'assembly-report.json': encoded(report),
                'preservation-final.json': encoded(preservation), 'kit-smoke-test.json': encoded(smoke),
                'target-proof.json': proof_bytes, 'springboard.elf': store['springboard.elf'],
                'store-SHA256SUMS.txt': sums(store), 'README.md': readme}
    for name in ('assemble_catalog_diagnostic.py', 'test_catalog_diagnostic_preservation.py',
                 'package_catalog_diagnostic.py', 'build_catalog_diagnostic_target.py'):
        evidence['product-sources/scripts/' + name] = (ROOT / 'scripts' / name).read_bytes()
    evidence['product-sources/catalog-diagnostic-release.yml'] = (ROOT / '.github/workflows/catalog-diagnostic-release.yml').read_bytes()
    for name, data in helpers.items():
        evidence['runtime-sources/' + name] = data
    for name in ('prepare.py', 'verify_readbacks.py', 'PRESERVING-UPDATE.txt'):
        evidence['kit-sources/' + name] = (DOCS / name).read_bytes()

    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / FACTORY).write_bytes(candidate)
    (args.output / 'README.md').write_bytes(readme)
    (args.output / 'RELEASE-NOTES.txt').write_text(body)
    (args.output / 'release.json').write_bytes(encoded(metadata))
    archive(args.output / (PREFIX + '-preserving-kit.zip'), kit)
    archive(args.output / (PREFIX + '-evidence.zip'), evidence)
    assets = {path.name: path.read_bytes() for path in args.output.iterdir() if path.is_file()}
    (args.output / 'SHA256SUMS.txt').write_bytes(sums(assets))
    print(json.dumps({'output': str(args.output), 'candidate_sha256': sha(candidate),
                      'assets': {name: sha(data) for name, data in sorted(assets.items())},
                      'preservation_banks': [0, 1], 'kit_smoke_test': smoke}, indent=2))


if __name__ == '__main__':
    main()
