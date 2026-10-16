#!/usr/bin/env python3
"""Exercise the pinned shared Home renderer/controller, including sanitizers."""
import argparse, json, os, subprocess, sys
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from package_native_faces import PINS, encoded, require, sha, verify_watch_source
p=argparse.ArgumentParser(description=__doc__)
for n in ('watch','system','utilities','output'): p.add_argument('--'+n,type=Path,required=True)
a=p.parse_args();w=a.watch.resolve();s=a.system.resolve();u=a.utilities.resolve();o=a.output.resolve();o.mkdir(parents=True,exist_ok=True)
inputs=verify_watch_source(w)
common=['--system-apps',str(s),'--utilities',str(u)]
cases=[
 ('packed-face-bytes','test_packed_alpha.py',[]),
 ('packed-calendar-bytes','test_packed_calendar.py',[]),
 ('packed-atlas-codec','test_packed_atlas_codec.py',[]),
 ('packed-atlas-render','test_packed_atlas_render.py',[]),
 ('native-faces','test_native_faces.py',[]),
 ('native-effects','test_native_effects.py',[]),
 ('native-height','test_home_native_height.py',[]),
 ('crown-lifecycle','test_crown_native_lifecycle.py',common),
 ('atomic-preferences','test_atomic_preferences.py',['--system',str(s),'--utilities',str(u),'--output',str(o/'atomic')]),
 ('crash-report','test_crash_report.py',['--output',str(o/'crash')]),
 ('native-gestures','test_clock_raster_gestures.py',[*common,'--native','--output',str(o/'gestures')]),
]
for width,height in ((240,240),(410,502),(502,410),(120,150)):
 cases.append((f'fast-wake-{width}x{height}','test_fast_wake_clock.py',[*common,'--width',str(width),'--height',str(height),'--atomic','--crash-report']))
def execute(case):
 label,script,args=case
 command=[sys.executable,str(w/'scripts'/script),*args]
 result=subprocess.run(command,capture_output=True,text=True,env={**os.environ,'ASAN_OPTIONS':'detect_leaks=0','PYTHONDONTWRITEBYTECODE':'1'})
 log=result.stdout+result.stderr;(o/(label+'.log')).write_text(log)
 if result.returncode:
  print(log,file=sys.stderr);raise RuntimeError('Home qualification failed: '+label)
 print(label+': PASS',flush=True)
 return {'case':label,'passed':True,'log_sha256':sha(log.encode()),'command':command}
with ThreadPoolExecutor(max_workers=3) as executor:
 results=list(executor.map(execute,cases))
require(inputs==verify_watch_source(w),'Watch source changed during qualification')
(o/'qualification.json').write_bytes(encoded({'watch_revision':PINS['watch_revision'],'system_revision':PINS['system_revision'],'utilities_revision':PINS['utilities_revision'],'source_sha256':inputs,'cases':results,'passed':True,'normal_and_sanitized':True,'hardware_tested':False}))
