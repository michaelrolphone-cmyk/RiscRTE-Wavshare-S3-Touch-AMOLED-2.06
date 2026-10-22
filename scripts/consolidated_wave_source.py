#!/usr/bin/env python3
"""Admit the exact flattened source union without changing historical inputs."""
import hashlib
import os
from pathlib import Path
import stat
import subprocess

BASE = '31ef3e34ffafddd4bb1a6ff4ed6e0f91236f6bb8'
CAPTURE = '788cfa532e06fb9661412dd3df174adc16daac3c'
PRODUCT = '07cb64541edc54dc88de65e98a619b59b16a82bc'
LOGGING_BASE = '9a98e763d783d795fc441b50adabe80d03341ed8'
ROOT = Path(__file__).resolve().parents[1]
NEW = {'scripts/consolidated_wave_source.py', 'tests/test_consolidated_wave_source.py',
       'docs/consolidation/20261022.json', '.github/workflows/consolidated-wave.yml'}
INTEGRATION = NEW | {'scripts/qualify_t039_wave_product.py',
    'scripts/qualify_t039_xtensa_relocations.py', 'tests/test_t039_wave_product.py',
    '.github/workflows/t039-wave-product.yml', '.github/workflows/t039-xtensa-relocation.yml',
    'scripts/package_serial_logging.py', '.github/workflows/serial-logging-native.yml'}


def require(ok, message):
    if not ok:
        raise ValueError(message)


def git(root, *args):
    env = {k:v for k,v in os.environ.items() if not k.startswith('GIT_')}
    env.update(GIT_NO_REPLACE_OBJECTS='1', GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL=os.devnull)
    return subprocess.check_output(['git', '-C', str(root), '--work-tree='+str(Path(root).resolve()),
        '-c', 'core.fsmonitor=false', '-c', 'core.ignoreStat=false', '-c', 'gc.auto=0',
        '-c', 'maintenance.auto=false', '-c', 'core.excludesFile='+os.devnull, *args], env=env)


def inventory(root, revision):
    result = {}
    for row in git(root, 'ls-tree', '-rz', revision).split(b'\0'):
        if not row: continue
        info, path = row.split(b'\t', 1)
        mode, kind, blob = info.decode().split()
        require(kind == 'blob', 'Unexpected non-file source')
        result[path.decode()] = (mode, blob)
    return result


def validate_trees(base, capture, current):
    additions = set(capture) - set(base)
    require(len(additions) == 49 and set(base) <= set(capture), 'Original capture coverage differs')
    require(all(capture[p] == entry for p, entry in base.items()), 'Original capture changes main')
    require(set(current) == set(capture) | NEW, 'Missing or unadmitted source path')
    for path, identity in capture.items():
        if path not in INTEGRATION:
            require(current[path] == identity, 'Preserved source differs: ' + path)
    require(all(current[p][0] in ('100644', '100755') for p in INTEGRATION), 'Invalid integration mode')


def validate_working(root, current):
    root = Path(root).resolve()
    for name, (expected_mode, expected_blob) in current.items():
        path = root / name
        require(path.resolve().is_relative_to(root), 'Source escapes checkout: '+name)
        mode = path.lstat().st_mode
        require(stat.S_ISREG(mode), 'Nonregular working source: '+name)
        actual_mode = '100755' if mode & stat.S_IXUSR else '100644'
        data = path.read_bytes()
        blob = hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()
        require((actual_mode, blob) == (expected_mode, expected_blob), 'Working source differs: '+name)


def clean(root, expected=None):
    root = Path(root).resolve()
    require(Path(git(root, 'rev-parse', '--show-toplevel').decode().strip()).resolve() == root,
            'Redirected source checkout')
    require(all(row.startswith(b'H ') for row in git(root, 'ls-files', '-v').splitlines()),
            'Hidden index source entry')
    require(not git(root, 'status', '--porcelain', '--untracked-files=all', '--ignore-submodules=none').strip(),
            'Dirty source checkout')
    head = git(root, 'rev-parse', 'HEAD').decode().strip()
    require(expected is None or head == expected, 'Wrong source head')
    current = inventory(root, 'HEAD')
    validate_working(root, current)
    # Only byte-verified root output rules may exclude untracked inputs.
    exclusions = ['--exclude-from='+str(root/'.gitignore')] if '.gitignore' in current else []
    require(not git(root, 'ls-files', '--others', *exclusions).strip(),
            'Untracked or locally ignored source entry')
    return head


def validate(root=ROOT, expected=None):
    head = clean(root, expected)
    validate_trees(inventory(root, BASE), inventory(root, CAPTURE), inventory(root, 'HEAD'))
    return head


def product_root():
    path = ROOT / '.source/released-product'
    clean(path, PRODUCT)
    return path


def historical_contract(path, digest):
    # An immutable old recipe remains historical, not an assertion about current main.
    data = git(ROOT, 'show', LOGGING_BASE+':'+path)
    require(hashlib.sha256(data).hexdigest() == digest, 'Historical recipe changed: '+path)


if __name__ == '__main__':
    print(validate())
