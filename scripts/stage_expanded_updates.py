#!/usr/bin/env python3
"""Add qualified shared update apps and disabled product providers to a new store."""
import argparse,hashlib,json,shutil
from pathlib import Path
p=argparse.ArgumentParser()
for name in ('store','apps','providers','baseline','output'):p.add_argument('--'+name,type=Path,required=True)
a=p.parse_args()
if a.output.exists():raise ValueError('Choose a fresh output directory')
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
shutil.copytree(a.store,a.output);(a.output/'cohort.json').unlink()
boot=json.loads((a.output/'boot.json').read_text());base=json.loads((a.baseline/'boot.json').read_text())
expected={'ota_update':'75ee1e4309be58714f3844d41d1ea704f552dd4701c755dc4be9d2999d5c01be','app_store':'e02746823ee7939d8be41ce2ef8533642070f41a577e02464ea29014d16667b2'}
for name in expected:
 elf=a.apps/(name+'.elf');assert sha(elf)==expected[name]
 receipt=json.loads((a.apps/(name+'-build.json')).read_text());assert receipt['sources']['system']['commit']=='e90ce6d4c81f89f918b88330368f390241255b59';assert not any(v['tracked_dirty'] for v in receipt['sources'].values())
 manifest=json.loads((a.apps/(name+'.json')).read_text());manifest['display_name']='Firmware Update' if name=='ota_update' else 'App Store';manifest['icon']='solid:f019' if name=='ota_update' else 'solid:f00a'
 row=next(x for x in base['app_capabilities'] if x['manifest']==name+'.json')
 for cap in ('input.power-key','power.sleep','display.power'):
  req={'capability':cap,'api':1};grant={**req,'instance_id':0}
  if req not in manifest['requires']:manifest['requires'].append(req)
  if grant not in row['grants']:row['grants'].append(grant)
 assert not any(x['manifest']==row['manifest'] for x in boot['app_capabilities']);boot['app_capabilities'].append(row)
 (a.output/(name+'.json')).write_text(json.dumps(manifest,indent=2)+'\n');shutil.copy2(elf,a.output/elf.name)
for name,digest in [('software-update-firmware','40151d532e4788d2ddfe5b4cd98569fdde49eb67f7bde1a460f60437570273a5'),('software-update-apps','cfc121f1ebb49f44d67190fb1cb75c61ebcdb01f227a39cb6fe18af31cf9900b')]:
 src=a.providers/name;assert sha(src/'driver.elf')==digest;dst=a.output/name;dst.mkdir()
 for f in ('driver.elf','manifest.json'):shutil.copy2(src/f,dst/f)
 boot['drivers'].append({'manifest':name+'/manifest.json'})
(a.output/'boot.json').write_text(json.dumps(boot,indent=2)+'\n')
for f in a.store.rglob('*'):
 if f.is_file() and f.name not in ('boot.json','cohort.json'):assert f.read_bytes()==(a.output/f.relative_to(a.store)).read_bytes()
assert all(x in boot['app_capabilities'] for x in json.loads((a.store/'boot.json').read_text())['app_capabilities'])
print('Preserved all existing store files except additive boot graph; 25 apps and 34 providers staged, new cohort binding required')
