#!/usr/bin/env python3
"""Flatten pinned test SDK headers with explicit, hash-checked Runtime overrides.

Duplicated #pragma once headers cannot safely be included from multiple source
roots. Runtime owns the newer storage/provider ABI; Watch supplies missing
board-driver helpers. This staging directory is for host integration tests only.
"""
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def assemble(sources, expected_overrides, output):
    selected, overrides = {}, {}
    for owner, root, folders in sources:
        for folder in folders:
            for path in sorted((root / folder).glob('*.h')):
                raw = path.read_bytes()
                record = {'owner': owner, 'path': path.relative_to(root).as_posix(),
                          'sha256': hashlib.sha256(raw).hexdigest()}
                if path.name in selected and selected[path.name][0]['sha256'] != record['sha256']:
                    overrides[path.name] = {'previous': selected[path.name][0], 'selected': record}
                selected[path.name] = record, raw
    if overrides != expected_overrides:
        raise ValueError('SDK override closure differs from reviewed pinned header hashes')
    if output.exists() and any(output.iterdir()):
        raise ValueError('SDK output must be empty')
    output.mkdir(parents=True, exist_ok=True)
    for name, (_, raw) in selected.items():
        (output / name).write_bytes(raw)
    return {'schema': 1, 'headers': {name: value[0] for name, value in sorted(selected.items())},
            'overrides': overrides}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('watch', 'runtime', 'output'):
        parser.add_argument('--' + name, required=True, type=Path)
    args = parser.parse_args()
    spec = json.loads((ROOT / 'docs/provider-ci/header-overrides.json').read_text())
    result = assemble([
        ('watch', args.watch.resolve(), ['sdk/driver', 'sdk/app', 'include']),
        ('runtime', args.runtime.resolve(), ['sdk/driver', 'sdk/app', 'sdk/hardware']),
    ], spec['overrides'], args.output.resolve())
    for name in ('RiscStorageWorkerV1.h', 'RiscStorageAsyncAdapterV1.h',
                 'RiscStorageNativeCapacityV1.h', 'RiscStorageSessionAdmissionV1.h',
                 'RiscStorageExportV1.h', 'TWatchPlatformV1.h', 'RiscI2cBusV1.h'):
        if name not in result['headers']:
            raise ValueError('Missing integration SDK header: ' + name)
    if (args.output / 'RiscStorageVolumeV1.h').read_bytes() != (ROOT / 'include/RiscStorageVolumeV1.h').read_bytes():
        raise ValueError('Product storage ABI prefix differs from pinned Runtime')
    result['source_pins'] = {key: spec[key] for key in ('watch_revision', 'runtime_revision')}
    (args.output / 'provenance.json').write_text(json.dumps(result, indent=2) + '\n')
    print(f"Provider integration SDK: {len(result['headers'])} headers, {len(result['overrides'])} reviewed overrides PASS")


if __name__ == '__main__':
    main()
