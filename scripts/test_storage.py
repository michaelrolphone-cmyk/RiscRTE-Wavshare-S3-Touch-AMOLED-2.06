#!/usr/bin/env python3
"""Test the actual SDMMC provider and FatFs with copied RAM card operations."""
import argparse,os,re,subprocess,tempfile
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--watch',type=Path,required=True);p.add_argument('--sdk',type=Path,help='Flattened pinned integration SDK');p.add_argument('--sanitize',action='store_true');a=p.parse_args()
r=Path(__file__).resolve().parents[1];w=a.watch.resolve()
with tempfile.TemporaryDirectory() as td:
 target=Path(td)/'storage'
 flags=['-fsanitize=address,undefined','-fno-omit-frame-pointer'] if a.sanitize else []
 subprocess.run([os.environ.get('CC','cc'),'-std=c11','-g','-Wall','-Wextra','-Werror','-Wno-misleading-indentation','-Wno-overflow','-Wno-unused-function',*flags,
  *['-I'+str(q) for q in ([a.sdk.resolve(),r/'include'] if a.sdk else [w/'sdk/driver',w/'include',r/'include'])],str(r/'tests/test_storage.c'),
  *[str(r/'lib/storage_fatfs/fatfs'/(f+'.c')) for f in ['ff','ffunicode']],'-o',str(target)],check=True)
 result=subprocess.check_output([str(target)],text=True);print(result,end='',flush=True)
 maximum=int(re.search(r'WRITE_CUTS=(\d+)',result)[1])
 for cut in range(1,maximum+1):subprocess.run([str(target),str(cut)],check=True)
