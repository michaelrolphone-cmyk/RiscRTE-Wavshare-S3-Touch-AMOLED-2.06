#!/usr/bin/env python3
"""Replace only Files in a sealed cumulative store; preserve every existing grant."""
import argparse,hashlib,json,shutil
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
for name in ('store','files','output'):p.add_argument('--'+name,type=Path,required=True)
a=p.parse_args()
def read(path):return json.loads(path.read_text())
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
assert not a.output.exists()
record=read(a.files/'file_browser-build-record.json')
assert sha(a.files/'file_browser.elf')==record['sha256']
for flag in ('PORTABLE_TEXT_INPUT_POLICY','PORTABLE_FILE_BROWSER_SOURCE_HANDOFF','PORTABLE_FILE_BROWSER_SHARED_INPUT','PORTABLE_WATCH_NATIVE_HEIGHT','PORTABLE_FILE_BROWSER_TERTIARY_INSTANCE=12'):
 assert '-D'+flag in record['defines'],flag
old=read(a.store/'file_browser.json');new=read(a.files/'file_browser.json')
assert old['id']==new['id']=='file_browser'
assert all(row in new['requires'] for row in old['requires'])
assert len(new['requires'])<=32
boot=read(a.store/'boot.json')
grant=next(row for row in boot['app_capabilities'] if row['manifest']=='file_browser.json')
assert all(row in grant['grants'] for row in record['required_grants'])
assert len(grant['grants'])<=32
shutil.copytree(a.store,a.output);(a.output/'cohort.json').unlink()
old['version']=new['version']
for row in new['requires']:
 if row not in old['requires']:old['requires'].append(row)
(a.output/'file_browser.json').write_text(json.dumps(old,separators=(',',':'))+'\n')
shutil.copy2(a.files/'file_browser.elf',a.output/'file_browser.elf')
changed={'cohort.json','file_browser.elf','file_browser.json'}
for path in a.store.rglob('*'):
 if path.is_file() and path.relative_to(a.store).as_posix() not in changed:
  assert path.read_bytes()==(a.output/path.relative_to(a.store)).read_bytes()
assert len(boot['app_capabilities'])==25 and len(boot['drivers'])==35
receipt={'runtime':'5561cc7bb09d1e2b03aafaecb8c95f0470f351f6','files':record,'all_prior_grants_unchanged':True,'all_other_payloads_unchanged':True,'apps':25,'providers':35,'hardware_tested':False}
(a.output.parent/'stage.json').write_text(json.dumps(receipt,indent=2)+'\n')
print('Files policy staged; 25 apps/35 providers, all grants and other payloads unchanged')
