#!/usr/bin/env python3
"""Run the source-pinned shared app custody regressions and record their results."""
import argparse
import io
import json
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
from package_crash_sdr import PINS, encoded, require, run, sha

SDK = {
    'RiscRuntimeV1.h': '80198965ebe3dda4d9cadbb5a6d64a44016041e8c2f610a6f636d915c6851831',
    'RiscRealtimeV1.h': '639781f728841cda6d40c3033877436b9e5d59519a4b15e11a9bc99b2365395d',
    'RiscAppDataV1.h': '9eb18840ea691f88e85cca6ede3de4833467745ec29225a51a58cb84c0aac84e',
    'AlarmServiceV1.h': 'c70c087550306c123255e1ace41aeb504809e16b0193e382ec8dfbd7cb5531f5',
    'AlarmServiceV2.h': 'd7e750a8093e1b5e698483254edc38533b7242a3446d0bca5866c9dfd6ad07a1',
}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('system', 'runtime', 'utilities', 'baseline-system', 'output'):
        p.add_argument('--' + name, type=Path, required=True)
    a = p.parse_args()
    require(__debug__, 'Do not run with Python -O')
    require(not a.output.exists() or not any(a.output.iterdir()), 'Fresh qualification output required')
    a.output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='crash-regression-sources-') as td:
        roots = {}
        for label, repo, revision in (
            ('system', a.system, PINS['system_revision']),
            ('runtime', a.runtime, PINS['runtime_revision']),
            ('utilities', a.utilities, PINS['utilities_revision']),
            ('baseline', a.baseline_system, PINS['regression_baseline_system']),
        ):
            require(run('git', '-C', repo, 'rev-parse', 'HEAD').strip() == revision, 'Qualification source HEAD mismatch: ' + label)
            root = Path(td) / label
            run('git', 'init', '-q', root)
            run('git', '-C', root, 'fetch', '--depth=1', repo.resolve(), revision)
            run('git', '-C', root, 'checkout', '-q', '--detach', 'FETCH_HEAD')
            require(run('git', '-C', root, 'rev-parse', 'HEAD').strip() == revision, 'Isolated source identity mismatch')
            roots[label] = root
        sdk = Path(td) / 'sdk'; sdk.mkdir()
        for name, digest in SDK.items():
            path = roots['runtime'] / 'sdk/app' / name if name.startswith('Risc') else roots['utilities'] / 'lib/Alarm/include' / name
            data = path.read_bytes(); require(sha(data) == digest, 'SDK input mismatch: ' + name)
            (sdk / name).write_bytes(data)
        receipts = {}
        for label, count in (('fixed', 192), ('baseline', 8)):
            command = [sys.executable, roots['system'] / 'scripts/test_shared_data_custody.py', '--sdk-include', sdk, '--app-data-sdk', sdk, '--utilities-root', roots['utilities'], '--output', a.output.resolve() / label]
            if label == 'fixed':
                command += ['--callback-audit']
            else:
                command += ['--source-root', roots['baseline'], '--test-source', roots['system'] / 'test/native_apps/shared_data_custody_test.c', '--baseline']
            (a.output / (label + '.log')).write_text(run(*command, cwd=roots['system']))
            receipt = json.loads((a.output / label / 'receipt.json').read_text())
            require(len(receipt['results']) == count and all(row['exit'] == 0 for row in receipt['results']), 'Regression result mismatch: ' + label)
            receipts[label] = receipt
    result = dict(system_revision=PINS['system_revision'], runtime_revision=PINS['runtime_revision'], utilities_revision=PINS['utilities_revision'], baseline_system_revision=PINS['regression_baseline_system'], sdk_sha256=SDK, fixed_cases=192, baseline_reproductions=8, source_checkouts_isolated=True, hardware_tested=False, receipts=receipts)
    (a.output / 'qualification.json').write_bytes(encoded(result))
    print(json.dumps(dict(fixed_cases=192, baseline_reproductions=8, passed=True)))


if __name__ == '__main__':
    main()
