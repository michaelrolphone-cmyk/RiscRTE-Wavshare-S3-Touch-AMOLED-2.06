#!/usr/bin/env python3
"""Compose T063 from exact published T054 bytes; preserve native and other features."""
from pathlib import Path
import argparse,hashlib,json,subprocess,sys
p=argparse.ArgumentParser()
for n in ('baseline','runtime','watch','product-repo','alarm','alarm-manifest','springboard','output'):p.add_argument('--'+n,type=Path,required=True)
a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True)
sys.path[:0]=[str(a.runtime.resolve()/'scripts'),str(a.watch.resolve()/'scripts')]
from spiffs_image import read_image
from paired_bank_images import initial_bank_state,parse_record
import current_bootfs
sha=lambda b:hashlib.sha256(b).hexdigest();enc=lambda v:(json.dumps(v,separators=(',',':'))+'\n').encode()
raw=a.baseline.read_bytes();baseline_sha='af789153d58cd1bc2c262f7d32cb1f225cd7d0426c859a43d772d3deb99f115b'
assert len(raw)==0x1000000 and sha(raw)==baseline_sha
size=0x550000;before=read_image(raw[0x2f0000:0x840000],size);assert current_bootfs.build(before,size=size)[0]==raw[0x2f0000:0x840000]
store=dict(before);store['alarm-service/driver.elf']=a.alarm.read_bytes();store['alarm-service/manifest.json']=enc(json.loads(a.alarm_manifest.read_bytes()))
assert json.loads(store['alarm-service/manifest.json'])['version']=='0.4.11'
store['springboard.elf']=a.springboard.read_bytes()
manifest=next(n for n,b in before.items() if n.endswith('.json') and b[:1]==b'{' and json.loads(b).get('file_name')=='springboard.elf')
m=json.loads(before[manifest]);v=m['version'].split('.');v[-1]=str(int(v[-1])+1);m['version']='.'.join(v);store[manifest]=enc(m)
cohort=json.loads(before['cohort.json']);assert cohort['version']=='0.1.36';fw=raw[0x10000:0x10000+cohort['firmware_size']];assert sha(fw)==cohort['firmware_sha256']
head=subprocess.check_output(['git','-C',a.product_repo,'rev-parse','HEAD'],text=True).strip();cohort.update(version='0.1.37',source_revision=head);store['cohort.json']=enc(cohort)
image,packing=current_bootfs.build(store,size=size);assert read_image(image,size)==store
state=initial_bank_state(fw,image,True,True);parse_record(state[:96],True,True)
full=bytearray(raw);full[0x2f0000:0x840000]=image;full[0xff2000:0xff2000+len(state)]=state
assert full[:0x2f0000]==raw[:0x2f0000] and full[0x840000:0xff2000]==raw[0x840000:0xff2000] and full[0xff3000:]==raw[0xff3000:]
changed=sorted(n for n in store if store[n]!=before[n]);assert set(changed)=={'alarm-service/driver.elf','alarm-service/manifest.json','springboard.elf',manifest,'cohort.json'}
name='Waveshare-0.1.37-T063-Startup-factory-erases-data-0x0.bin';(a.output/name).write_bytes(full)
for n,b in store.items():q=a.output/'store'/n;q.parent.mkdir(parents=True,exist_ok=True);q.write_bytes(b)
proof=dict(file=name,version='0.1.37',image_sha256=sha(full),baseline_sha256=baseline_sha,product_commit=head,native_sha256=sha(fw),native_unchanged=True,boot_grants_unchanged=True,settings_partitions_unchanged=True,all_other_store_files_unchanged=True,changed_store_files=changed,packing=packing,hardware_tested=False,inventory={n:sha(b) for n,b in store.items()})
(a.output/'assembly-report.json').write_text(json.dumps(proof,indent=2)+'\n');print(json.dumps({k:v for k,v in proof.items() if k!='inventory'},indent=2))
