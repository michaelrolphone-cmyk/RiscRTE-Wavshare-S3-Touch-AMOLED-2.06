#!/usr/bin/env python3
"""Add explicit package grants without changing existing app identities/data."""
import argparse,json,hashlib,shutil
from pathlib import Path
p=argparse.ArgumentParser()
for key in ['baseline','home','catalog','internal','output']:p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args();boot=json.loads((a.baseline/'boot.json').read_text());before=json.loads(json.dumps(boot))
assert boot.get('installation')=={'grants':[],'volume_instance':12},'Unexpected baseline installation authority'
assert len(boot['drivers'])==36
entry=next(x for x in boot['app_capabilities'] if x['manifest']=='default.json')
for cap,instance in [('software.installed-apps',0),('storage.key-value',6)]:
 grant={'capability':cap,'api':1,'instance_id':instance}
 if grant not in entry['grants']:entry['grants'].append(grant)
boot['drivers'] += [{'manifest':'installed-apps/manifest.json','app_data':[{'name':'installed.apps','namespace':2000,'access':'read-write'}]}, {'manifest':'pkg-internal/manifest.json'}]
envelope=[{'capability':cap,'api':api,'instance_id':instance} for cap,api,instance in [('display.output',1,5),('input.touch.raw',1,6),('board.battery',1,4),('alarm.service',1,0),('storage.volume',1,12),('runtime.realtime',1,0),('storage.key-value',1,0),('storage.app-data',1,0)]]
boot['installation'].update(internal_volume_instance=0,namespace_range={'first':3000,'count':128},grants=envelope,provider_grants=[g for g in envelope if g['capability'] not in ['storage.key-value','storage.app-data']])
# Existing app grants, private namespaces and driver selections are preserved.
for old,new in zip(before['app_capabilities'],boot['app_capabilities']):
 assert old==new or (old['manifest']=='default.json' and all(g in new['grants'] for g in old['grants']))
assert boot['drivers'][:36]==before['drivers']
shutil.copytree(a.baseline,a.output)
for name in ['default.elf','default.json']:shutil.copyfile(a.home/name,a.output/name)
for source,target in [(a.catalog,'installed-apps'),(a.internal,'pkg-internal')]:
 (a.output/target).mkdir()
 for name in ['driver.elf','manifest.json']:shutil.copyfile(source/name,a.output/target/name)
(a.output/'boot.json').write_text(json.dumps(boot,separators=(',',':'))+'\n')
print('Preserved36 drivers/all existing app policies; explicit catalog/cache/private namespace and package media grants composed. Complete admission remains required.')
