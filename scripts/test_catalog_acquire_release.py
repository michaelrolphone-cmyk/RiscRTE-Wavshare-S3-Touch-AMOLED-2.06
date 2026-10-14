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
DOCS = ROOT / 'docs/t063-catalog-acquire'
spec = importlib.util.spec_from_file_location('package_catalog_acquire', ROOT / 'scripts/package_catalog_acquire.py')
module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)

def run_failure(command):
    r = subprocess.run(command, capture_output=True, text=True)
    if r.returncode == 0:
        raise AssertionError('Invalid fixture was accepted')
    return r

with tempfile.TemporaryDirectory(prefix='catalog-acquire-guards-') as td:
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
    run_failure([sys.executable, '-O', str(ROOT / 'scripts/package_catalog_acquire.py'), '--baseline', str(root / 'baseline.bin'), '--runtime', str(root), '--native', str(root), '--image-helper', str(root), '--vendor', str(root), '--source-revision', '0'*40, '--output', str(root / 'out')])
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
markers = ('RTE_SOURCE=' + module.PINS['runtime_revision'], 'RISC_PAIRED_STORE_ABI:3', 'RISC_APP_POLICY_ROWS:32', 'RISC_APP_REQUIREMENT_ROWS:32', 'esp32s3-16mb-waveshare-expanded')
payload = b'\0\0\x02\x4f' + b'\0' * 20 + b''.join(m.encode() + b'\0' for m in markers)
fixture = {'firmware.bin': payload, 'firmware.elf': payload}
module.verify_native_identity(fixture)
for name in ('firmware.bin', 'firmware.elf'):
    for original, replacement in ((module.PINS['runtime_revision'].encode(), b'0' * 40), (b'RISC_PAIRED_STORE_ABI:3', b'RISC_PAIRED_STORE_ABI:2'), (b'RISC_APP_POLICY_ROWS:32', b'RISC_APP_POLICY_ROWS:16')):
        changed = dict(fixture); changed[name] = payload.replace(original, replacement)
        rejected(lambda: module.verify_native_identity(changed))
rejected(lambda: module.verify_native_identity(dict(fixture, **{'firmware.bin': b''})))
rejected(lambda: module.verify_native_identity(dict(fixture, **{'firmware.bin': b'\0' * 0x260001})))
print(json.dumps(dict(source_native_baseline_negative_cases=14, passed=True)))
