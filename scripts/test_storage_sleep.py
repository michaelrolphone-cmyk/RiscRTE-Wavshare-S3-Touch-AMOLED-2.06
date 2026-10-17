#!/usr/bin/env python3
"""Checked ordinary/async SD sleep lifecycle with actual provider/FatFs and RAM media."""
import argparse, os, subprocess, tempfile
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--sdk',type=Path,required=True)
p.add_argument('--support-include',type=Path,required=True)
p.add_argument('--sanitize',action='store_true')
a=p.parse_args();root=Path(__file__).resolve().parents[1]
cases=('healthy','absent-boot','absent-resume','unformatted','sync-failure','close-failure',
       'unlock-failure','resume-close-failure','resume-read-failure','legacy')
with tempfile.TemporaryDirectory(prefix='wave-sd-sleep-') as tmp:
 for asynchronous in (0,1):
  target=Path(tmp)/('sleep-'+str(asynchronous))
  flags=['-fsanitize=address,undefined','-fno-sanitize-recover=all','-fno-omit-frame-pointer','-no-pie'] if a.sanitize else []
  subprocess.run([os.environ.get('CC','cc'),'-std=c11','-g','-Wall','-Wextra','-Werror',
   '-Wno-unused-function','-Wno-misleading-indentation','-Wno-overflow',*flags,'-DTEST_SLEEP_ASYNC='+str(asynchronous),
   *['-I'+str(q.resolve()) for q in (a.sdk,a.support_include,root/'include')],
   str(root/'tests/test_storage_sleep.c'),*[str(root/'lib/storage_fatfs/fatfs'/(f+'.c')) for f in ('ff','ffunicode')],
   '-o',str(target)],check=True)
  for case in cases:subprocess.run([str(target),case],check=True,timeout=30)
print('Ordinary/async checked SD sleep lifecycle: all cases PASS; host-only, no device qualification')
