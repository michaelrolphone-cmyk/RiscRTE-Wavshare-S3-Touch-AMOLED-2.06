#!/usr/bin/env python3
"""Compile real shared Home sleep policy against the actual Waveshare provider."""
import argparse, os, subprocess, tempfile
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
for name in ('watch','system','utilities'):
    p.add_argument('--'+name,type=Path,required=True)
p.add_argument('--provider-source',type=Path)
p.add_argument('--sanitize',action='store_true')
a=p.parse_args();root=Path(__file__).resolve().parents[1]
flags=['-std=c11','-Wall','-Wextra','-Werror','-Wno-misleading-indentation','-g']
if a.sanitize:flags+=['-fsanitize=address,undefined','-fno-sanitize-recover=all','-fno-omit-frame-pointer','-no-pie']
if a.provider_source:flags+=['-DPOWER_PROVIDER_SOURCE="'+str(a.provider_source.resolve())+'"']
includes=[a.utilities/'lib/Alarm/include',root/'include',a.watch/'sdk/driver',a.watch/'sdk/app',a.watch/'include',a.watch/'apps/clock',a.system/'lib/PortableApps/include']
with tempfile.TemporaryDirectory() as tmp:
    target=Path(tmp)/'test'
    subprocess.run([os.environ.get('CC','cc'),*flags,*['-I'+str(x) for x in includes],str(root/'tests/power_home_sleep_fixture.c'),'-o',str(target)],check=True)
    subprocess.run([str(target)],check=True)
