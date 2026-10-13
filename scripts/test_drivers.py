#!/usr/bin/env python3
"""Execute production driver code against register/transport models."""
import argparse,os,subprocess,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--watch',required=True,type=Path);p.add_argument('--sanitize',action='store_true');a=p.parse_args()
flags=['-std=c11','-Wall','-Wextra','-Werror','-Wno-misleading-indentation','-g']
if a.sanitize:flags+=['-fsanitize=address,undefined','-fno-omit-frame-pointer']
with tempfile.TemporaryDirectory() as tmp:
 for source in sorted((ROOT/'tests').glob('test_*.c')):
  if source.stem=='test_storage':continue
  target=Path(tmp)/source.stem
  subprocess.run([os.environ.get('CC','cc'),*flags,*['-I'+str(x) for x in (ROOT/'include',a.watch/'sdk/driver',a.watch/'sdk/app',a.watch/'include')],str(source),'-o',str(target)],check=True)
  subprocess.run([str(target)],check=True)
