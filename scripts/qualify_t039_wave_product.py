#!/usr/bin/env python3
"""Isolated T039 composition through the exact released Wave Runtime consumer.

Never writes a production input, installable RTE package, firmware, release, or
permission envelope. Host admission does not execute Xtensa instructions.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
BASE = '07cb64541edc54dc88de65e98a619b59b16a82bc'
DOCS = ROOT / 'docs/t039/product-candidate'
RECEIPT = 'qualification.json'
ADDITIONS = {'docs/t039/product-candidate/source-pins.json',
             'docs/t039/product-candidate/README.md',
             'scripts/qualify_t039_wave_product.py',
             'tests/test_t039_wave_product.py',
             '.github/workflows/t039-wave-product.yml'}
ELF = 'Apps/ble_buttons/ble_buttons.elf'
MIRROR = 'Apps/ble_buttons/manifest.json'
NOTICE = ('UNRELEASED T039 WAVESHARE PRODUCT CANDIDATE. NOT FOR INSTALLATION.\n'
          'Full host consumer admission is not target execution, live memory fit,\n'
          'physical BLE behavior, or hardware acceptance. No firmware is emitted.\n')


def require(ok, message):
    if not ok:
        raise ValueError(message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def record(data):
    return {'bytes': len(data), 'sha256': sha(data)}


def read(path):
    return json.loads(Path(path).read_bytes())


def write(path, value):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(value, sort_keys=True, indent=2) + '\n')


def git(root, *args):
    return subprocess.check_output(['git', '-C', str(root), *args])


def safe_name(name):
    p = PurePosixPath(name)
    require(name and not p.is_absolute() and '..' not in p.parts and
            str(p) == name and '\\' not in name, 'Unsafe path: ' + name)
    return name


def archive_files(path):
    with zipfile.ZipFile(path) as z:
        names = z.namelist()
        require(len(names) == len(set(names)), 'Duplicate archive members')
        result = {}
        for info in z.infolist():
            require(not ((info.external_attr >> 16) & 0o170000) == 0o120000,
                    'Archive symlink forbidden')
            if not info.is_dir():
                result[safe_name(info.filename)] = z.read(info)
        return result


def inventory(root):
    result = {}
    for p in sorted(root.rglob('*')):
        require(not p.is_symlink(), 'Artifact symlink forbidden')
        if p.is_file() and p.relative_to(root).as_posix() != RECEIPT:
            result[p.relative_to(root).as_posix()] = record(p.read_bytes())
    return result


def write_tree(root, files):
    for name, data in files.items():
        dest = root / safe_name(name)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)


def read_tree(root):
    require(root.is_dir(), 'Missing candidate namespace')
    return {p.relative_to(root).as_posix(): p.read_bytes()
            for p in root.rglob('*') if p.is_file()}


def source_guard(expected=None):
    from consolidated_wave_source import validate
    return validate(ROOT, expected)


def check_repo(path, pin):
    require(git(path, 'rev-parse', 'HEAD').decode().strip() == pin and
            not git(path, 'status', '--porcelain').strip(),
            'Dependency pin or tracked sources changed: ' + str(path))


def compose(before, external, elf, manifest, pins):
    require(record(elf) == pins['candidate_elf'] and
            record(manifest) == pins['candidate_manifest'], 'Candidate input bytes differ')
    old, new = json.loads(before['ble_buttons.json']), json.loads(manifest)
    require(old['version'] == '0.1.29' and new['version'] == '0.1.31' and
            {k: v for k, v in old.items() if k != 'version'} ==
            {k: v for k, v in new.items() if k != 'version'},
            'BLE manifest change exceeds candidate version')
    require(len(new['requires']) == 16, 'Candidate requirement count changed')
    boot = json.loads(before['boot.json'])
    rows = [r for r in boot['app_capabilities'] if r['manifest'] == 'ble_buttons.json']
    require(len(rows) == 1 and rows[0]['image_source'] == pins['image_source'],
            'Boot-owned source identity changed')
    require(new['file_name'] not in before and ELF in external and MIRROR in external,
            'BLE app no longer uses the selected external path')
    require(len(rows[0]['grants']) == 17, 'Retained BLE owner grant count differs')
    require(json.loads(external[MIRROR]) == old, 'Baseline BLE manifest mirror differs')
    after = dict(before, **{'ble_buttons.json': manifest})
    payload = dict(external, **{ELF: elf, MIRROR: manifest})
    require(set(after) == set(before) and set(payload) == set(external), 'Namespace inventory changed')
    require([n for n in after if after[n] != before[n]] == ['ble_buttons.json'],
            'Unexpected internal composition delta')
    require({n for n in payload if payload[n] != external[n]} == {ELF, MIRROR},
            'Unexpected external composition delta')
    require(after['boot.json'] == before['boot.json'], 'Boot authority changed')
    return after, payload


def verify(root, source, receipt_digest):
    source_guard(source)
    require(sha((root / RECEIPT).read_bytes()) == receipt_digest, 'Receipt digest mismatch')
    q = read(root / RECEIPT)
    require(q['source_commit'] == source and q['baseline_source'] == BASE and
            q['source_tree'] == git(ROOT, 'rev-parse', 'HEAD^{tree}').decode().strip(),
            'Source identity changed')
    require(q['artifact_inventory'] == inventory(root), 'Transported artifact changed')
    require((root / 'CANDIDATE_ONLY.txt').read_text() == NOTICE, 'Candidate notice changed')
    require(all(q[k] is False for k in ('firmware_emitted', 'release_published',
            'production_pins_changed', 'boot_grants_changed', 'target_instructions_executed',
            'live_memory_fit_verified', 'hardware_qualified')), 'Qualification scope changed')
    pins = read(DOCS / 'source-pins.json')
    before, external = read_tree(root / 'baseline/store'), read_tree(root / 'baseline/external')
    after, payload = compose(before, external, (root / 'candidate/external' / ELF).read_bytes(),
                              (root / 'candidate/store/ble_buttons.json').read_bytes(), pins)
    require(read_tree(root / 'candidate/store') == after and
            read_tree(root / 'candidate/external') == payload, 'Candidate composition differs')
    require(len(before) == 111 and len(external) == 45, 'Complete product namespaces required')
    require(q['consumer_runtime'] == pins['runtime_revision'], 'Wrong consumer Runtime')
    require(q['status'] in ('host-product-admission-qualified', 'consumer-rejected', 'qualification-blocked'), 'Unknown result')
    if q['status'] == 'host-product-admission-qualified':
        require([r['sanitized'] for r in q['full_admission']] == [False, True],
                'Distinct normal and sanitized full admission required')
        for row in q['full_admission']:
            require(row['prepared'] and row['cohort_validated'] and row['elf_count'] == 43 and
                    row['app_policy_rows'] == 32 and row['active_platform_count'] == 22 and
                    row['candidate_platform_count'] == 22 and not row['hardware_calls'] and
                    not row['storage_calls'], 'Full real consumer admission missing')
            negative = row['unauthorized_namespace_control']
            require(not negative['cohort_validated'] and negative['expected_rejection'] and
                    negative['prepared'] and negative['elf_count'] == 0 and
                    not negative['hardware_calls'] and not negative['storage_calls'],
                    'Existing namespace rejection gate missing')
        require(len(q['full_admission']) == 2 and q['external_admission']['external_app_count'] == 22,
                'Incomplete normal/sanitized product admission')
        external_proof = q['external_admission']
        require(external_proof['runtime_commit'] == pins['runtime_revision'] and
                external_proof['native_elf_sha256'] == q['native_elf']['sha256'],
                'External admission uses another consumer')
        require(len(external_proof['apps']) == 22 and
                {r['path'] for r in external_proof['apps']} ==
                {n for n in payload if n.endswith('.elf')}, 'External app coverage differs')
        for app in external_proof['apps']:
            require(app['elf'] == record(payload[app['path']]) and
                    [t['sanitized'] for t in app['tests']] == [False, True],
                    'External bytes or normal/sanitized evidence differ')
            for t in app['tests']:
                require(t['production_application_admission'] and t['production_structural_validation'] and
                        t['driver_role_rejected'] and t['unsafe_rejected'] and
                        t['missing_import_rejections'] == len(app['imports']) and
                        t['malformed_or_truncated_rejections'] == 4 and
                        t['production_removable_image_snapshots'] == 2 and
                        not t['target_instructions_executed'],
                        'External ELF rejection/snapshot controls missing')
    else:
        require(q.get('failure') and (root / 'consumer-rejection.txt').is_file(), 'Rejection evidence missing')
    return q


def build(args):
    source = source_guard(); pins = read(DOCS / 'source-pins.json')
    out = args.output.resolve(); require(not out.exists(), 'Output must be new')
    from consolidated_wave_source import product_root
    released_product = product_root()
    product_pins = read(released_product / 'docs/serial-transfer-mode/source-pins.json')
    for name in ('runtime', 'image_helper'):
        check_repo(getattr(args, name), product_pins[name + '_revision'])
    sdk_file = args.sdk / 'components/soc/esp32s3/include/soc/soc_caps.h'
    require(sha(sdk_file.read_bytes()) == pins['sdk_gpio_header_sha256'], 'Pinned SDK GPIO source differs')
    for name in ('store.bin', 'sd-apps.zip', 'source-lock.json', 'qualification.json'):
        require(record((args.baseline / name).read_bytes()) == pins['baseline_assets'][name],
                'Published baseline differs: ' + name)
    evidence = args.baseline / 'evidence.zip'
    require(record(evidence.read_bytes()) == pins['baseline_assets']['Waveshare-0.1.64-SD-Apps-Evidence.zip'],
            'Released native evidence archive differs')
    native_lock = read(args.baseline / 'source-lock.json')
    with zipfile.ZipFile(evidence) as z:
        native = z.read('build/riscrte_native.elf')
    require(record(native) == {k: native_lock['native_files']['firmware_elf'][k]
                              for k in ('bytes', 'sha256')}, 'Released native ELF differs')
    require(sha(args.utilities_archive.read_bytes()) == pins['utilities_archive_sha256'],
            'PR98 transported archive differs')
    with zipfile.ZipFile(args.utilities_archive) as z:
        elf, manifest = z.read('app/ble_buttons.elf'), z.read('app/ble_buttons.json')
        upstream = json.loads(z.read('candidate-package.json'))
    require(upstream['source_commit'] == pins['utilities_source'] and
            upstream['version'] == '0.1.31', 'Utilities source/version differs')
    sys.path.insert(0, str(args.image_helper / 'scripts'))
    from read_only_spiffs import read_image
    before = read_image((args.baseline / 'store.bin').read_bytes(), 0x550000)
    external = archive_files(args.baseline / 'sd-apps.zip')
    require(len(before) == 111 and len(external) == 45, 'Incomplete released namespaces')
    after, payload = compose(before, external, elf, manifest, pins)
    out.mkdir(parents=True)
    (out / 'CANDIDATE_ONLY.txt').write_text(NOTICE)
    for label, files in [('baseline/store', before), ('baseline/external', external),
                         ('candidate/store', after), ('candidate/external', payload)]:
        write_tree(out / label, files)
    for name in ADDITIONS:
        write_tree(out / 'source/product', {name: (ROOT / name).read_bytes()})
    write(out / 'upstream-candidate-receipt.json', upstream)
    write(out / 'baseline-release-input-lock.json', native_lock)
    q = {'schema': 1, 'source_commit': source,
         'source_tree': git(ROOT, 'rev-parse', 'HEAD^{tree}').decode().strip(),
         'baseline_source': BASE, 'baseline_release_id': pins['baseline_release_id'],
         'consumer_runtime': pins['runtime_revision'], 'utilities_source': pins['utilities_source'],
         'upstream_archive_sha256': pins['utilities_archive_sha256'],
         'native_elf': record(native), 'candidate_elf': record(elf), 'candidate_manifest': record(manifest),
         'internal_changed': ['ble_buttons.json'], 'external_changed': [ELF, MIRROR],
         'retained_internal_files': 110, 'retained_external_files': 43,
         'boot_grants_changed': False, 'firmware_emitted': False, 'release_published': False,
         'production_pins_changed': False, 'target_instructions_executed': False,
         'live_memory_fit_verified': False, 'hardware_qualified': False,
         'full_admission': [], 'ci': {k: os.environ.get(k) for k in
             ('GITHUB_RUN_ID', 'GITHUB_RUN_ATTEMPT', 'GITHUB_SHA', 'GITHUB_REPOSITORY')},
         'limits': 'Host full boot/cohort policy and compiled-native ELF admission only; no target instructions, allocation feasibility, device, radio or physical outcomes.'}
    sources = {'runtime': args.runtime, 'product': released_product, 'image_helper': args.image_helper, 'sdk': args.sdk}
    sys.path.insert(0, str(released_product / 'scripts'))
    try:
        from serial_transfer_qualification import admit_product
        for sanitized in (False, True):
            q['full_admission'].append(admit_product(sources, native, before, after,
                read(args.baseline / 'qualification.json')['native'], sanitized=sanitized,
                receipt_dir=out / 'full-admission'))
        from qualify_minimal_sd_elfs import qualify
        q['external_admission'] = qualify(args.runtime, args.image_helper, native, after, payload,
                                         out / 'external-admission')
        q['status'] = 'host-product-admission-qualified'
    except (ValueError, subprocess.SubprocessError, ImportError, OSError) as e:
        # Never relabel a real refusal as success or alter grants to get a pass.
        q['status'] = ('consumer-rejected' if isinstance(e, ValueError) and
            str(e).startswith('Production cohort admission failed:') else 'qualification-blocked')
        q['failure'] = str(e)
        (out / 'consumer-rejection.txt').write_text(str(e) + '\n')
    q['artifact_inventory'] = inventory(out)
    write(out / RECEIPT, q)
    verify(out, source, sha((out / RECEIPT).read_bytes()))
    print(json.dumps({'status': q['status'], 'receipt_sha256': sha((out / RECEIPT).read_bytes())}))
    if q['status'] != 'host-product-admission-qualified':
        raise SystemExit('Consumer rejected candidate; preserved receipt is not a qualification pass')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    commands = p.add_subparsers(dest='action', required=True)
    b = commands.add_parser('build')
    for name in ('baseline', 'runtime', 'image-helper', 'sdk', 'utilities-archive', 'output'):
        b.add_argument('--' + name, type=lambda s: Path(s).resolve(), required=True)
    v = commands.add_parser('verify')
    v.add_argument('--artifact', type=Path, required=True)
    v.add_argument('--source-sha', required=True)
    v.add_argument('--receipt-sha256', required=True)
    a = p.parse_args()
    if a.action == 'build':
        build(a)
    else:
        q = verify(a.artifact, a.source_sha, a.receipt_sha256)
        print('Transported product candidate verified: ' + q['status'])


if __name__ == '__main__':
    main()
