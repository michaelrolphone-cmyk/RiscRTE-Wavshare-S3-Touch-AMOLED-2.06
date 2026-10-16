#!/usr/bin/env python3
"""Offline release source/kit guard tests; no device access or publication."""
import ast
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / 'docs/t030-native-ui'
spec = importlib.util.spec_from_file_location('package_native_ui', ROOT / 'scripts/package_native_ui.py')
module = importlib.util.module_from_spec(spec); sys.modules[spec.name] = module; spec.loader.exec_module(module)

def run_failure(command):
    r = subprocess.run(command, capture_output=True, text=True)
    if r.returncode == 0:
        raise AssertionError('Invalid fixture was accepted')
    return r

with tempfile.TemporaryDirectory(prefix='native-ui-guards-') as td:
    root = Path(td)
    for name in ('prepare.py', 'verify_readbacks.py'):
        (root / name).write_bytes((DOCS / name).read_bytes())
    data = b'fixture readback bytes'
    (root / 'firmware.bin').write_bytes(data)
    (root / 'selection.bin').write_bytes(data)
    rows = [dict(file='firmware.bin', bytes=len(data), sha256=hashlib.sha256(data).hexdigest()), dict(file='selection.bin', bytes=len(data), sha256=hashlib.sha256(data).hexdigest())]
    (root / 'plan.json').write_text(json.dumps(dict(writes=rows)))
    passed = 0
    for optimized in (False, True):
        python = [sys.executable] + (['-O'] if optimized else [])
        for selection in (False, True):
            command = [*python, str(root / 'verify_readbacks.py'), '--plan', str(root / 'plan.json'), '--readbacks', str(root)] + (['--selection'] if selection else [])
            subprocess.run(command, check=True, capture_output=True); passed += 1
            target = root / ('selection.bin' if selection else 'firmware.bin')
            for corrupt in (data + b'X', bytes([data[0] ^ 1]) + data[1:]):
                target.write_bytes(corrupt); run_failure(command); passed += 1
            target.write_bytes(data)
        for corrupt in ('baseline', 'candidate'):
            (root / 'baseline.bin').write_bytes(b'baseline')
            (root / 'candidate.bin').write_bytes(b'candidate')
            metadata = {name + '_sha256': hashlib.sha256((root / (name + '.bin')).read_bytes()).hexdigest() for name in ('baseline', 'candidate')}
            (root / 'release.json').write_text(json.dumps(metadata))
            (root / (corrupt + '.bin')).write_bytes(b'corrupted')
            failed = run_failure([*python, str(root / 'prepare.py'), '--snapshot', str(root / 'baseline.bin'), '--output', str(root / 'plan-out')])
            assert corrupt + ' integrity mismatch' in failed.stderr
            passed += 1
    for n in (1, 2):
        module.archive(root / f'test{n}.zip', {'two.txt': b'2', 'one.txt': b'1'})
    assert (root / 'test1.zip').read_bytes() == (root / 'test2.zip').read_bytes()
    with zipfile.ZipFile(root / 'test1.zip') as z:
        assert z.namelist() == ['SHA256SUMS.txt', 'one.txt', 'two.txt']
        assert all(i.date_time == (1980, 1, 1, 0, 0, 0) for i in z.infolist())
    run_failure([sys.executable, '-O', str(ROOT / 'scripts/package_native_ui.py'), '--baseline', str(root / 'baseline.bin'), '--runtime', str(root), '--native', str(root), '--system', str(root), '--bridges', str(root), '--compiler', str(root), '--image-helper', str(root), '--vendor', str(root), '--source-revision', '0'*40, '--output', str(root / 'out')])
    passed += 1
print(json.dumps(dict(passed=True, kit_guard_cases=passed, deterministic_archive=True, device_accessed=False)))

def rejected(call):
    try:
        call()
    except (ValueError, subprocess.CalledProcessError, FileNotFoundError):
        return
    raise AssertionError('Invalid release input was accepted')

# Source-owned inputs must exist in the exact selected commit, never just disk.
with tempfile.TemporaryDirectory(prefix='catalog-source-guards-') as td:
    root = Path(td)
    subprocess.run(['git', 'init', '-q', str(root)], check=True)
    (root / 'owned.txt').write_text('owned')
    subprocess.run(['git', '-C', str(root), 'add', 'owned.txt'], check=True)
    subprocess.run(['git', '-C', str(root), '-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid', 'commit', '-qm', 'Fixture'], check=True)
    revision = subprocess.check_output(['git', '-C', str(root), 'rev-parse', 'HEAD'], text=True).strip()
    assert module.verify_product_source(root, revision, ['owned.txt'])
    rejected(lambda: module.verify_product_source(root, '0' * 40, ['owned.txt']))
    (root / 'untracked.txt').write_text('untracked')
    rejected(lambda: module.verify_product_source(root, revision, ['untracked.txt']))
    rejected(lambda: module.verify_product_source(root, revision, ['missing.txt']))
    (root / 'owned.txt').write_text('dirty')
    rejected(lambda: module.verify_product_source(root, revision, ['owned.txt']))
rejected(lambda: module.verify_baseline_bytes(b'wrong baseline'))
rejected(lambda: module.verify_baseline_bytes(b'\xff' * 0x1000000))
module.PINS['runtime_revision'] = module.PINS['baseline_runtime']
markers = ('RTE_SOURCE=' + module.PINS['runtime_revision'], 'RISC_PAIRED_STORE_ABI:3', 'RISC_APP_POLICY_ROWS:32', 'RISC_APP_REQUIREMENT_ROWS:32', 'esp32s3-16mb-waveshare-expanded', 'RISCRTE_VENDOR_DISPLAY_TIMING_V1')
payload = b'\0\0\x02\x4f' + b'\0' * 20 + b''.join(m.encode() + b'\0' for m in markers)
fixture = {'firmware.bin': payload, 'firmware.elf': payload}
module.verify_native_identity(fixture)
for name in ('firmware.bin', 'firmware.elf'):
    for original, replacement in ((module.PINS['runtime_revision'].encode(), b'0' * 40), (b'RISC_PAIRED_STORE_ABI:3', b'RISC_PAIRED_STORE_ABI:2'), (b'RISC_APP_POLICY_ROWS:32', b'RISC_APP_POLICY_ROWS:16'), (b'RISCRTE_VENDOR_DISPLAY_TIMING_V1', b'RISCRTE_VENDOR_DISPLAY_TIMING_V0')):
        changed = dict(fixture); changed[name] = payload.replace(original, replacement)
        rejected(lambda: module.verify_native_identity(changed))
rejected(lambda: module.verify_native_identity(dict(fixture, **{'firmware.bin': b''})))
rejected(lambda: module.verify_native_identity(dict(fixture, **{'firmware.bin': b'\0' * 0x260001})))
print(json.dumps(dict(source_native_baseline_negative_cases=16, passed=True)))

# Pending release pins must fail closed, even while harmless helper tests pass.
module.PINS['finalized'] = False
rejected(module.verify_final_pins)
module.PINS.update(finalized=True, system_revision=module.PINS['baseline_system'], native_changed=True,
                   springboard_manifest_version='1.7.17', changed_product_native_inputs=[])
module.verify_final_pins()
for key, value in [('runtime_revision', 'pending'), ('system_revision', None), ('native_changed', None),
                   ('springboard_manifest_version', None), ('changed_store_files', ['cohort.json']),
                   ('changed_product_native_inputs', ['unexpected.cpp']),
                   ('add_springboard_flags', []), ('remove_springboard_flags', ['-DPORTABLE_FORCE_FULL_FRAMES'])]:
    original = module.PINS[key]; module.PINS[key] = value
    rejected(module.verify_final_pins); module.PINS[key] = original
module.PINS['native_changed'] = False
rejected(module.verify_final_pins); module.PINS['native_changed'] = True

before = {f'app-{i}.elf': b'preserved ELF' for i in range(60)}
before.update({'springboard.elf': b'baseline springboard', 'springboard.json': b'{"version":"1.7.16","capabilities":["retained"]}', 'cohort.json': b'baseline cohort'})
before.update({'default.elf': b'preserved home', 'default.json': json.dumps({'type':'application','id':'twatch-clock','file_name':'default.elf','requires':[]}).encode(), 'boot.json': json.dumps({'app_capabilities':[{'manifest':'default.json','grants':[]}]}).encode()})
module.PINS['baseline_home_sha256'] = module.sha(before['default.elf'])
new_elf = b'\x7fELF\x01\x01\x01' + b'\0' * 9 + b'\x03\x00\x5e\x00' + b'new ELF'
store = module.replace_springboard(before, new_elf); store['cohort.json'] = b'candidate cohort'
assert module.verify_changed_store(before, store) == ['boot.json', 'cohort.json', 'default.json', 'springboard.elf', 'springboard.json']
for name in before:
    if name not in module.PINS['changed_store_files']:
        assert store[name] == before[name]
for changed in (dict(store, **{'app-0.elf': b'changed'}), dict(store, extra=b'new'),
                {k: v for k, v in store.items() if k != 'app-0.elf'},
                dict(store, **{'springboard.json': b'{"version":"1.7.17"}'}),
                dict(store, **{'boot.json': before['boot.json']}),
                dict(store, **{'default.json': before['default.json']}),
                dict(store, **{'default.elf': b'changed home'})):
    rejected(lambda: module.verify_changed_store(before, changed))
rejected(lambda: module.replace_springboard(before, before['springboard.elf']))
rejected(lambda: module.replace_springboard(before, b'invalid ELF'))
print(json.dumps(dict(final_pin_negative_cases=10, store_preservation_negative_cases=9, preserved_elf_count=61, passed=True)))

# Profile staging has only one approved byte delta; reject existing wrong bytes.
from native_ui_profile import profile_bytes, verify_profile, PROFILE_NAME
with tempfile.TemporaryDirectory(prefix='native-ui-profile-guards-') as td:
    root = Path(td)
    subprocess.run(['git', 'init', '-q', str(root)], check=True)
    base = b'[platformio]\nextra_configs = platformio.ini\n[env:waveshare-t051]\nbuild_flags =\n  -DRISC_NATIVE_STORAGE_CUSTODY=1\n'
    (root / 'expanded-candidate.ini').write_bytes(base)
    subprocess.run(['git', '-C', str(root), 'add', '.'], check=True)
    subprocess.run(['git', '-C', str(root), '-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid', 'commit', '-qm', 'Profile fixture'], check=True)
    module.PINS['baseline_runtime'] = subprocess.check_output(['git', '-C', str(root), 'rev-parse', 'HEAD'], text=True).strip()
    expected = base + b'  -DRISC_PERFORMANCE_TRACE=1\n  -DRISC_PERFORMANCE_TRACE_CAPACITY=64\n'
    assert profile_bytes(root) == expected
    (root / PROFILE_NAME).write_bytes(expected)
    assert verify_profile(root) == hashlib.sha256(expected).hexdigest()
    (root / PROFILE_NAME).write_bytes(expected.replace(b'TRACE=1', b'TRACE=0'))
    rejected(lambda: verify_profile(root))
    (root / 'expanded-candidate.ini').write_bytes(base + b'  -DUNEXPECTED=1\n')
    rejected(lambda: profile_bytes(root))
print(json.dumps(dict(native_profile_positive_cases=2, native_profile_negative_cases=2, passed=True)))

# A matching vendor HEAD is insufficient: reject ignored and untracked sources.
with tempfile.TemporaryDirectory(prefix='native-ui-vendor-guards-') as td:
    root = Path(td)
    source = root / 'examples/arduino/libraries/Arduino_GFX'
    source.mkdir(parents=True)
    (source / 'owned.cpp').write_text('source')
    (source / '.gitignore').write_text('ignored.cpp\n')
    subprocess.run(['git', 'init', '-q', str(root)], check=True)
    subprocess.run(['git', '-C', str(root), 'add', '.'], check=True)
    subprocess.run(['git', '-C', str(root), '-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid', 'commit', '-qm', 'Vendor fixture'], check=True)
    revision = subprocess.check_output(['git', '-C', str(root), 'rev-parse', 'HEAD'], text=True).strip()
    assert module.verify_vendor_tree(root, revision)
    for name in ('extra.cpp', 'ignored.cpp'):
        path = source / name; path.write_text('unowned')
        rejected(lambda: module.verify_vendor_tree(root, revision)); path.unlink()
    (source / 'owned.cpp').write_text('modified')
    rejected(lambda: module.verify_vendor_tree(root, revision))
    (source / 'owned.cpp').write_text('source')
    (source / 'alias.cpp').symlink_to('owned.cpp')
    rejected(lambda: module.verify_vendor_tree(root, revision))
print(json.dumps(dict(vendor_archive_positive_cases=1, vendor_archive_negative_cases=4, passed=True)))

# Vector scan conversion uses np_pixel physically; native_watch_pixel rescales.
from qualify_native_ui_sources import verify_profile_raster_row
good_profile = dict(frames=240, render_calls=240, instrument_calls=[0]*16)
good_profile['instrument_calls'][5] = 1747387
verify_profile_raster_row(good_profile)
profile_negative = 0
for key in ('frames', 'render_calls'):
    row = dict(good_profile, **{key: 239})
    rejected(lambda: verify_profile_raster_row(row)); profile_negative += 1
for index, value in ((5, 0), (5, -1), (6, 1)):
    row = dict(good_profile, instrument_calls=list(good_profile['instrument_calls']))
    row['instrument_calls'][index] = value
    rejected(lambda: verify_profile_raster_row(row)); profile_negative += 1
for calls in ([], [0]*6, [0]*17):
    rejected(lambda: verify_profile_raster_row(dict(good_profile, instrument_calls=calls))); profile_negative += 1
print(json.dumps(dict(native_raster_profile_positive_cases=1, native_raster_profile_negative_cases=profile_negative, passed=True)))
