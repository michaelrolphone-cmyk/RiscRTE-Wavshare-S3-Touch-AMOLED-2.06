#!/usr/bin/env python3
"""Execute standalone production driver tests against register/transport models.

Storage integration tests need additional source files and SDKs. Their dedicated
runners are invoked separately by providers.yml, never as standalone C programs.
"""
import argparse
import os
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPECIALIZED = {
    'test_storage': 'test_storage.py',
    'test_storage_async': 'test_storage_async.py',
    'test_storage_export': 'test_storage_export.py',
    'test_usb_storage': 'test_usb_storage.py',
}


def standalone_sources(root=ROOT):
    return [source for source in sorted((root / 'tests').glob('test_*.c'))
            if source.stem not in SPECIALIZED]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--watch', required=True, type=Path)
    parser.add_argument('--sanitize', action='store_true')
    args = parser.parse_args()
    flags = ['-std=c11', '-Wall', '-Wextra', '-Werror',
             '-Wno-misleading-indentation', '-g']
    if args.sanitize:
        flags += ['-fsanitize=address,undefined', '-fno-omit-frame-pointer']
    includes = [ROOT / 'include', args.watch / 'sdk/driver',
                args.watch / 'sdk/app', args.watch / 'include']
    with tempfile.TemporaryDirectory() as tmp:
        for source in standalone_sources():
            target = Path(tmp) / source.stem
            subprocess.run([os.environ.get('CC', 'cc'), *flags,
                            *['-I' + str(x) for x in includes], str(source),
                            '-o', str(target)], check=True)
            subprocess.run([str(target)], check=True)


if __name__ == '__main__':
    main()
