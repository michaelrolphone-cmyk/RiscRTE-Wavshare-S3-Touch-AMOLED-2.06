#!/usr/bin/env python3
"""Replace only the scene provider with the qualified full-profile component."""
import argparse,hashlib,importlib.util,json,shutil,subprocess,sys
from pathlib import Path

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def load(n,p):
 s=importlib.util.spec_from_file_location(n,p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m

def main():
 p=argparse.ArgumentParser(description=__doc__)
 for k in ('store','system','runtime','shared','cc','output'):p.add_argument('--'+k,type=Path,required=True)
 a=p.parse_args()
 for k,v in vars(a).items():setattr(a,k,v.resolve())
 for repo,pin in ((a.system,'f4b30f8ebcc6d8cb905c8e90c91b1691acbe8165'),(a.shared,'ec768c7fae6fdb484fef28c6ec87f129b0a7f585')):
  assert subprocess.check_output(['git','-C',str(repo),'rev-parse','HEAD'],text=True).strip()==pin
  assert not subprocess.check_output(['git','-C',str(repo),'diff','HEAD','--name-only'],text=True).strip()
 if a.output.exists():raise ValueError('Choose a new output')
 font=a.system/'Services/scene_host/fonts/telemetry.inc'
 if not font.is_file() or sha(font)!='2d7501e42d6223ebbc191817715431182c435fea944a1a02166a0748a577eaf1':
  raise ValueError('Qualified telemetry.inc required (Pillow output differs across host platforms)')
 a.output.mkdir(parents=True);shutil.copytree(a.store,a.output/'store')
 sdk=load('qualified_scene_sdk',a.system/'scripts/scene_sdk.py');inc=sdk.stage_sdk(a.runtime,a.system,a.output/'sdk')
 mapping=a.output/'scene.map';mapping.write_text('{ global: t5_driver_get; local: *; };\n');elf=a.output/'scene.elf'
 command=[str(a.cc),'-std=c11','-Os','-fPIC','-mtext-section-literals','-mlongcalls','-fvisibility=hidden','-ffreestanding','-fno-builtin','-nostdlib','-nostartfiles','-shared','-Wl,--no-relax','-Wl,--hash-style=sysv','-Wl,--version-script='+str(mapping),'-Wall','-Wextra','-Werror','-Wno-misleading-indentation','-ffunction-sections','-fdata-sections','-Wl,--gc-sections','-I'+str(inc),str(a.system/'Services/scene_host/host.c'),'-lgcc','-o',str(elf)]
 subprocess.run(command,check=True)
 assert elf.stat().st_size==480824,(elf.stat().st_size,sha(elf))
 sys.path.insert(0,str(a.shared/'scripts'));from compact_current_elf import compact
 compaction=compact(elf,str(a.cc),debug_path=a.output/'scene-original.elf')
 assert elf.stat().st_size==310220 and sha(elf)=='017039a424e0482cf35c062a5b883af621bda0457e8bb9ff321fe63640e54fa1'
 shutil.copy2(elf,a.output/'store/ui-scene/driver.elf')
 manifest=json.loads((a.system/'Services/scene_host/manifest.json').read_text());manifest['requires']=[r for r in manifest['requires'] if r['capability']!='input.navigation']
 (a.output/'store/ui-scene/manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
 changed=[]
 for old in a.store.rglob('*'):
  if old.is_file() and old.read_bytes()!=(a.output/'store'/old.relative_to(a.store)).read_bytes():changed.append(str(old.relative_to(a.store)))
 assert sorted(changed)==['ui-scene/driver.elf','ui-scene/manifest.json'],changed
 (a.output/'scene-build.json').write_text(json.dumps({'system_pin':'f4b30f8ebcc6d8cb905c8e90c91b1691acbe8165','command':command,'compaction':compaction,'manifest':manifest,'changed_files':changed,'flashable':False,'hardware_verified':False},indent=2)+'\n')
 print(json.dumps(compaction,indent=2))
if __name__=='__main__':main()
