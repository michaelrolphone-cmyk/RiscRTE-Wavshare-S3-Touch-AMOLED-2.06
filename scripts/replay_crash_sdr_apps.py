#!/usr/bin/env python3
"""Replay all 17 repaired apps from the published System recipe and record custody."""
import argparse
import io
import json
from pathlib import Path
import subprocess
import sys
import tarfile
from package_crash_sdr import APPS, PINS, encoded, git_bytes, require, run, sha


def verify_receipt(receipt, root, spec, source_files, compiler):
    require(receipt['product'] == 'wave' and receipt['source_inputs_verified'] is True, 'Replay source verification failed')
    require(set(receipt['apps']) == set(APPS), 'Replay did not build the complete 17-app set')
    require(receipt['driver_sha256'] == source_files['scripts/replay_shared_crash_apps.py'], 'Replay driver mismatch')
    expected = {Path(name).name: digest for name, digest in source_files.items() if name.startswith('docs/shared-app-crashes/replay/')}
    require(receipt['spec_sha256'] == expected, 'Replay specification closure mismatch')
    require(receipt['compiler'] == PINS['compiler_version'] and receipt['compiler_sha256'] == sha(compiler.read_bytes()), 'Replay compiler mismatch')
    require(receipt['repositories'] == spec['repositories'], 'Replay repository pins changed')
    for name, row in APPS.items():
        built = receipt['apps'][name]
        data = (root / (name + '.elf')).read_bytes()
        require(sha(data) == row['sha256'] == built['sha256'] and len(data) == row['bytes'] == built['bytes'], 'Replayed ELF mismatch: ' + name)
    return receipt


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('system', 'compiler', 'output'):
        p.add_argument('--' + name, type=Path, required=True)
    p.add_argument('--source-cache', type=Path)
    a = p.parse_args()
    require(__debug__, 'Do not run with Python -O')
    require(not a.output.exists() or not any(a.output.iterdir()), 'Fresh replay output required')
    system = a.system.resolve()
    require(run('git', '-C', system, 'rev-parse', 'HEAD').strip() == PINS['system_revision'], 'Replay source HEAD mismatch')
    require(not run('git', '-C', system, 'diff', 'HEAD', '--name-only').strip(), 'Replay tracked source is dirty')
    a.output.mkdir(parents=True, exist_ok=True)
    selected = ['scripts/replay_shared_crash_apps.py', 'docs/shared-app-crashes/replay']
    data = subprocess.check_output(['git', '-C', str(system), 'archive', PINS['system_revision'], '--', *selected])
    source = a.output / 'recipe'
    source.mkdir()
    with tarfile.open(fileobj=io.BytesIO(data)) as archive:
        require(all(member.isfile() or member.isdir() for member in archive), 'Unsupported replay source member')
        archive.extractall(source, filter='data')
    files = {path.relative_to(source).as_posix(): sha(path.read_bytes()) for path in source.rglob('*') if path.is_file()}
    spec = json.loads((source / 'docs/shared-app-crashes/replay/inputs.json').read_text())
    recipes = json.loads((source / 'docs/shared-app-crashes/replay/wave.json').read_text())
    require(set(recipes) == set(APPS), 'Published replay set differs from qualified cohort')
    for name, row in APPS.items():
        require(all(recipes[name][key] == row[key] for key in ('sha256', 'bytes')), 'Published replay output changed: ' + name)
    require(any(row['commit'] == PINS['repair_system_revision'] for row in spec['repositories'].values()), 'Repair System source pin absent')
    apps = a.output / 'apps'
    cmd = [sys.executable, source / selected[0], '--product', 'wave', '--compiler', a.compiler.resolve(), '--output', apps]
    if a.source_cache:
        cmd += ['--source-cache', a.source_cache.resolve()]
    run(*cmd)
    receipt = json.loads((apps / 'receipt.json').read_text())
    verify_receipt(receipt, apps, spec, files, a.compiler.resolve())
    proof = dict(system_revision=PINS['system_revision'], repair_system_revision=PINS['repair_system_revision'], recipe_archive_sha256=sha(data), source_files=files, source_archive_isolated=True, complete=True, app_count=17, receipt=receipt)
    (a.output / 'qualification.json').write_bytes(encoded(proof))
    print(json.dumps(proof, indent=2))


if __name__ == '__main__':
    main()
