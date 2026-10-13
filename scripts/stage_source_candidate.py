#!/usr/bin/env python3
"""Stage source-capable Files/Viewer on an exact existing cumulative store."""
from pathlib import Path
import argparse,hashlib,json,shutil,sys
p=argparse.ArgumentParser(description=__doc__)
for name in ('store','files','viewer','output','compactor','cc'):p.add_argument('--'+name,type=Path,required=True)
a=p.parse_args();assert not a.output.exists()
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text())
def write(p,value):p.write_text(json.dumps(value,separators=(',',':'))+'\n')
shutil.copytree(a.store,a.output);(a.output/'cohort.json').unlink()
boot=read(a.store/'boot.json');prior=read(a.store/'boot.json')
files=read(a.files/'file_browser-build-record.json');viewer=read(a.viewer/'build.json')
assert sha(a.files/'file_browser.elf')==files['sha256']
assert sha(a.viewer/'model_viewer.elf')==viewer['sha256']
assert '-DPORTABLE_FILE_BROWSER_SOURCE_HANDOFF' in files['defines']
assert '-DPORTABLE_FILE_BROWSER_TERTIARY_INSTANCE=12' in files['defines']
for name,folder in [('file_browser',a.files),('model_viewer',a.viewer)]:
 old=read(a.store/(name+'.json'));new=read(folder/(name+'.json'))
 old['version']=new['version']
 for declaration in new['requires']:
  if declaration not in old['requires']:old['requires'].append(declaration)
 assert {'capability':'file.open.source','api':1} in old['requires']
 write(a.output/(name+'.json'),old);shutil.copyfile(folder/(name+'.elf'),a.output/(name+'.elf'))
 row=next(x for x in boot['app_capabilities'] if x['manifest']==name+'.json')
 grants=files['required_grants'] if name=='file_browser' else [{'capability':'file.open.source','api':1,'instance_id':0}]
 for grant in grants:
  if grant not in row['grants']:row['grants'].append(grant)
 assert len(row['grants'])<=32
write(a.output/'boot.json',boot)
sys.path.insert(0,str(a.compactor.resolve()));from compact_current_elf import compact
compaction=compact(a.output/'model_viewer.elf',str(a.cc),debug_path=a.output.parent/'model-viewer-source-original.elf')
assert compaction['retained_loader_sections_symbols_relocations_unchanged']
changed={'cohort.json','boot.json','file_browser.json','file_browser.elf','model_viewer.json','model_viewer.elf'}
for f in a.store.rglob('*'):
 if f.is_file() and str(f.relative_to(a.store)) not in changed:assert f.read_bytes()==(a.output/f.relative_to(a.store)).read_bytes()
for row in prior['app_capabilities']:
 now=next(x for x in boot['app_capabilities'] if x['manifest']==row['manifest']);assert all(g in now['grants'] for g in row['grants'])
assert len(boot['app_capabilities'])==25 and len(boot['drivers'])==35
(a.output.parent/'source-stage.json').write_text(json.dumps({'files':files,'viewer':viewer,'viewer_compaction':compaction,'preserved_all_other_store_bytes':True,'preserved_all_prior_grants':True,'hardware_tested':False,'store':{str(f.relative_to(a.output)):sha(f) for f in a.output.rglob('*') if f.is_file()}},indent=2)+'\n')
print('Source stage: all25apps/35providers, prior grants and other payloads preserved; Files/Viewer replaced; viewer loader semantics checked')
