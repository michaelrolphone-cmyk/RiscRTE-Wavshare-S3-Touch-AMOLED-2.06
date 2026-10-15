#!/usr/bin/env python3
"""Generate the sole .44 native profile delta over the source-owned .43 profile."""
import argparse
import hashlib
from pathlib import Path
import subprocess

PROFILE_NAME = 'native-ui-candidate.ini'
EXTRA_FLAGS = ('-DRISC_PERFORMANCE_TRACE=1', '-DRISC_PERFORMANCE_TRACE_CAPACITY=64')


def profile_bytes(runtime):
    from package_native_ui import PINS, require
    base = (runtime / 'expanded-candidate.ini').read_bytes()
    expected = subprocess.check_output(['git', '-C', str(runtime), 'show',
                                       PINS['baseline_runtime'] + ':expanded-candidate.ini'])
    require(base == expected, 'Baseline expanded profile changed')
    require(base.endswith(b'  -DRISC_NATIVE_STORAGE_CUSTODY=1\n'), 'Unexpected baseline profile tail')
    require(all(flag.encode() not in base for flag in EXTRA_FLAGS), 'Performance flag already present')
    return base + ''.join('  ' + flag + '\n' for flag in EXTRA_FLAGS).encode()


def verify_profile(runtime):
    expected = profile_bytes(runtime)
    actual = (runtime / PROFILE_NAME).read_bytes()
    if actual != expected:
        raise ValueError('Generated .44 native profile differs from source-owned recipe')
    return hashlib.sha256(actual).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime', type=Path, required=True)
    args = parser.parse_args()
    target = args.runtime / PROFILE_NAME
    data = profile_bytes(args.runtime)
    if target.exists() and target.read_bytes() != data:
        raise ValueError('Refusing to overwrite a different native profile')
    target.write_bytes(data)
    print(str(target) + ' SHA-256=' + verify_profile(args.runtime))


if __name__ == '__main__':
    main()
