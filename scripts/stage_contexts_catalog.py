#!/usr/bin/env python3
"""Add qualified Contexts and its missing text provider to a new local store."""
import argparse, hashlib, importlib.util, json, shutil, subprocess, sys
from pathlib import Path

def load(name,path):
 s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,v):p.write_text(json.dumps(v,indent=2)+'\n')
def main():
 p=argparse.ArgumentParser(description=__doc__)
 for key in ('store','contexts-build','scene-system','runtime','helper','shared','output'):p.add_argument('--'+key,type=Path,required=True)
 a=p.parse_args()
 for k,v in vars(a).items():setattr(a,k,v.resolve())
 for repo,pin in ((a.scene_system,'f4b30f8ebcc6d8cb905c8e90c91b1691acbe8165'),(a.helper,'362537417c4f37bbb240879d5ba756686511fec1'),(a.shared,'ec768c7fae6fdb484fef28c6ec87f129b0a7f585')):
  assert subprocess.check_output(['git','-C',str(repo),'rev-parse','HEAD'],text=True).strip()==pin
  assert not subprocess.check_output(['git','-C',str(repo),'diff','HEAD','--name-only'],text=True).strip()
 elf=a.contexts_build/'contexts/contexts.elf'
 assert elf.stat().st_size==88020 and sha(elf)=='8db9d4be5801635bdb58e3f5ddaa41bcbdb744243a0e875a4a8252496cd24402'
 if a.output.exists():raise ValueError('Choose a new output directory')
 a.output.mkdir(parents=True);raw=a.output/'unsealed-store';shutil.copytree(a.store,raw)
 sdk=load('contexts_provider_sdk',a.scene_system/'scripts/scene_sdk.py');inc=sdk.stage_sdk(a.runtime,a.scene_system,a.output/'sdk')
 for n in ('RiscUsbHidV1.h','RiscUsbControllerV1.h','RiscUsbProviderV1.h'):shutil.copy2(a.scene_system/'Services/text_input'/n,inc/n)
 shutil.copy2(a.scene_system/'sdk/app/RiscTextEntryV1.h',inc/'RiscTextEntryV1.h')
 builder=load('contexts_provider_builder',a.scene_system/'scripts/scene_build.py');manifest=json.loads((a.scene_system/'Services/text_input/manifest.json').read_text())
 receipt=builder.build(builder.compiler_path(),inc,a.output/'text-input',manifest,[a.scene_system/'Services/text_input/host.c'])
 sys.path.insert(0,str(a.shared/'scripts'));from compact_current_elf import compact
 receipt['compaction']=compact(a.output/'text-input/driver.elf',builder.compiler_path(),debug_path=a.output/'text-input/debug.elf')
 target=raw/'text-input';target.mkdir();shutil.copy2(a.output/'text-input/driver.elf',target/'driver.elf');write(target/'manifest.json',manifest)
 boot=json.loads((raw/'boot.json').read_text());boot['drivers'].append({'manifest':'text-input/manifest.json'})
 row=next(x for x in boot['app_capabilities'] if x['manifest']=='contexts.json')
 row['grants'].append({'capability':'ui.text-input','api':1,'instance_id':0})
 write(raw/'boot.json',boot)
 m=json.loads((a.contexts_build/'contexts/contexts.json').read_text())
 # Keep the canonical optional capability declaration. This composition needs
 # generic Runtime optional-manifest support; do not downgrade it to requires.
 allowed={'type','id','version','architecture','file_name','entry','requires','display_name','icon','min_firmware_version','optional'}
 m={k:v for k,v in m.items() if k in allowed}
 # The pinned helper predates optional declarations. Give it its supported
 # schema, then restore canonical optional rows in the staged result below.
 helper_manifest={k:v for k,v in m.items() if k!='optional'}
 write(raw/'contexts.json',helper_manifest);shutil.copy2(elf,raw/'contexts.elf')
 profile={'schema':1,'entries':[],'consumers':['contexts.json']};write(a.output/'presentation.json',profile)
 subprocess.run([sys.executable,str(a.helper/'scripts/stage_app_catalog_metadata.py'),'--store',str(raw),'--profile',str(a.output/'presentation.json'),'--requirement-capacity','32','--grant-capacity','32','--output',str(a.output/'store')],check=True)
 # The older generic metadata helper promotes catalog to requires. Restore the
 # canonical optional record after it adds the explicit boot grant.
 staged=a.output/'store'/'contexts.json';final=json.loads(staged.read_text())
 catalog={'capability':'app.catalog','api':1}
 assert catalog in m.get('optional',[])
 final['requires']=[r for r in final['requires'] if r!=catalog]
 final['optional']=m['optional'];write(staged,final)
 preserved={}
 for driver in json.loads((a.store/'boot.json').read_text())['drivers']:
  path=Path(driver['manifest']);old=a.store/path.parent
  for f in old.iterdir():
   if f.is_file():
    relative=f.relative_to(a.store);assert f.read_bytes()==(a.output/'store'/relative).read_bytes();preserved[str(relative)]=sha(f)
 write(a.output/'composition.json',{'contexts_source':'186ba80899fc9746609860821df61c7bbe0e2dc8','contexts_sha256':sha(elf),'new_text_provider_system':'f4b30f8ebcc6d8cb905c8e90c91b1691acbe8165','text_provider':receipt,'existing_provider_files_preserved':preserved,'flashable':False,'hardware_verified':False,'pending':['whole-store admission','scene/text behavior on existing scene provider','remaining device composition']})
if __name__=='__main__':main()
