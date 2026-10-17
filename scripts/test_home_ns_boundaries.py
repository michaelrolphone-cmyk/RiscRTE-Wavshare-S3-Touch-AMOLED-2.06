#!/usr/bin/env python3
"""Bound production Home behavior under deferred serial checkpoint dispatch."""
from pathlib import Path
import argparse,subprocess,sys,os,json,hashlib,tempfile
root=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser(description=__doc__)
for name in ('watch','system','utilities','output'):p.add_argument('--'+name,type=Path,required=True)
a=p.parse_args();out=a.output.resolve();out.mkdir(parents=True,exist_ok=True);w=a.watch.resolve();s=a.system.resolve();u=a.utilities.resolve()
sys.path.insert(0,str(w/'scripts'));from merged_sdk import headers
pins={'watch':(w,'b00d4e7d36fc69c8defd250a82f6af077c732137'),'system':(s,'bb0cadf3cec3445a64e11513b47b2676f3fdd92d'),'utilities':(u,'4fdcad2495c33fe63f5f6faca9b11ced3c739a5b')}
for name,(path,expected) in pins.items():
 actual=subprocess.check_output(['git','-C',str(path),'rev-parse','HEAD'],text=True).strip()
 assert actual==expected, name+' source revision differs'
 assert not subprocess.check_output(['git','-C',str(path),'status','--porcelain','--untracked-files=no'],text=True).strip(), name+' tracked source differs'
receipt={'hardware_tested':False,'leak_sanitizer':False,'source_pins':{'watch':'b00d4e7d36fc69c8defd250a82f6af077c732137','system':'bb0cadf3cec3445a64e11513b47b2676f3fdd92d','utilities':'4fdcad2495c33fe63f5f6faca9b11ced3c739a5b'},'scope':'Production Home controllers with modeled device and Runtime API boundaries; sustained BUSY and explicit clean/context return controls. No native scheduler, target timing or physical cause claim.','cases':[],'inputs':{}}
with tempfile.TemporaryDirectory(prefix='wave-home-ns-build-') as temp:
 work=Path(temp);sdk=headers(work,s,u,w)
 original=w/'tests/fast_wake_clock_test.c'
 assert hashlib.sha256(original.read_bytes()).hexdigest()=="85292c7c79aba23e97780c324fe50e3744e321d3ac3a63774556024de493b778", 'Pinned Home fixture changed'
 text=original.read_text().replace('static const risc_runtime_api_v1 fast_runtime=', 'static risc_runtime_api_v1 fast_runtime=').replace('int main(void){','int inherited_fast_main(void){')
 assert text.count('ended=true;')==4, 'Pinned lifecycle fixture changed'
 text='#include <stdbool.h>\nstatic bool probe_long;\n'+text.replace('ended=true;', 'if(!probe_long)ended=true;')
 text+=(root/'tests/serial_stat_home/home_ns_controls.inc').read_text().replace('da.present_status','da.base.present_status')
 fixture=out/'home_ns.c';fixture.write_text(text)
 sources=[fixture,*[w/'apps/clock'/n for n in ['nova/nova.c','points_projection.c','viewport.c','capability_clients.c','quick_radios.c']],*[s/'lib/PortableApps/src'/n for n in ['quick_actions.c','quick_render.c','quick_session.c','PortableAutomaticProvision.c','PortableNetworkSession.c']]]
 for mode in ['normal','sanitized']:
  flags=['-O1','-g','-Wall','-Wextra','-Werror','-Wno-unused-function','-Wno-misleading-indentation','-DWATCH_COMPACT_NOVA_ASSETS','-DWATCH_SHARED_PREFERENCE_HEADERS','-DPORTABLE_LOW_BATTERY','-DWATCH_COMPRESSED_CALENDAR_ALPHA','-DWATCH_COMPRESSED_FACE_ALPHA','-DWATCH_FAST_WAKE','-DWATCH_COLD_BOOT_ANIMATION','-DPORTABLE_WATCH_NATIVE_HEIGHT','-DPORTABLE_RTC_UTC8_DENVER','-DPORTABLE_PREFERENCE_STORE','-DWATCH_ATOMIC_PREFERENCES','-DPORTABLE_QUICK_ATOMIC_PREFERENCES','-DPORTABLE_QUICK_RADIOS','-DWATCH_AUTOMATIC_PROVISION','-DWATCH_CRASH_REPORT','-DCRASH_REPORT_SESSION_FILES=1','-DWATCH_CRASH_REPORT_NAMESPACE=61','-DTEST_WIDTH=410u','-DTEST_HEIGHT=502u',*['-I'+str(p) for p in [sdk,w/'include',w,w/'tests',s/'lib/PortableApps/src']]]
  if mode=='sanitized':flags+=['-fsanitize=address,undefined','-fno-sanitize-recover=all','-fno-omit-frame-pointer','-no-pie']
  objects=[];commands=[]
  def run(command):
   command=list(map(str,command));commands.append(command);subprocess.run(command,check=True)
  for i,src in enumerate(sources):
   obj=work/f'home-{i}.o';dep=work/f'home-{i}.d';run(['cc','-std=c11',*flags,*(['-DWATCH_CONTEXTS_CLIENT'] if i else []),'-MMD','-MF',dep,'-c',src,'-o',obj]);objects.append(obj)
   for p in dep.read_text().replace('\\\n',' ').split(':',1)[1].split():receipt['inputs'][p]=hashlib.sha256(Path(p).read_bytes()).hexdigest()
  binary=work/'home';run(['c++','-std=c++17',*flags,w/'apps/clock/effects/boot.cpp',*objects,'-o',binary])
  (out/f'{mode}-commands.json').write_text(json.dumps(commands,indent=2)+'\n')
  for case in ['busy-continues','health-return','frame-return','context-return']:
   result=subprocess.run([str(binary),case],capture_output=True,text=True,env={**os.environ,'ASAN_OPTIONS':'detect_leaks=0','UBSAN_OPTIONS':'halt_on_error=1'},timeout=120)
   (out/f'{mode}-{case}.log').write_text(result.stdout+result.stderr);print(result.stdout+result.stderr,end='',flush=True);result.check_returncode();receipt['cases'].append({'build':mode,'case':case,'output':result.stdout})
 for source in (original,Path(__file__).resolve(),root/'tests/serial_stat_home/home_ns_controls.inc',w/'apps/clock/effects/boot.cpp'):
  receipt['inputs'][str(source)]=hashlib.sha256(source.read_bytes()).hexdigest()
(out/'qualification.json').write_text(json.dumps(receipt,indent=2)+'\n')

