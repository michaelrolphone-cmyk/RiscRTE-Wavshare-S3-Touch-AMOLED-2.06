#!/usr/bin/env python3
"""Exercise actual SDMMC/FatFs with a RAM card and copied worker mailbox.
Pass a unified SDK directory and the product DriverSupport include directory.
This test does not qualify native lifecycle, profile encoding, or hardware.
"""
import argparse, os, subprocess, tempfile
from pathlib import Path
p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--sdk', type=Path, required=True)
p.add_argument('--support-include', type=Path, required=True)
p.add_argument('--sanitize', action='store_true')
a = p.parse_args()
r = Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory() as td:
    target = Path(td) / 'storage-async'
    flags = ['-fsanitize=address,undefined', '-fno-omit-frame-pointer'] if a.sanitize else []
    subprocess.run([os.environ.get('CC', 'cc'), '-std=c11', '-g', '-Wall', '-Wextra', '-Werror',
        '-Wno-unused-function', '-Wno-misleading-indentation', '-Wno-overflow', *flags,
        *['-I' + str(q.resolve()) for q in [a.sdk, a.support_include, r / 'include']],
        str(r / 'tests/test_storage_async.c'),
        *[str(r / 'lib/storage_fatfs/fatfs' / (f + '.c')) for f in ['ff', 'ffunicode']],
        '-o', str(target)], check=True)
    subprocess.run([str(target)], check=True)
