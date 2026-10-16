#!/usr/bin/env python3
"""Correct Waterfall startup without changing the restored shared Springboard."""
import argparse,hashlib,json,subprocess,sys
from pathlib import Path
from spectrum_storage_policy import provision
from shared_springboard_selection import verify as verify_springboard
p=argparse.ArgumentParser(description=__doc__)
for n in ('baseline','waterfall','runtime','watch-product','output'):p.add_argument('--'+n,type=Path,required=True)
a=p.parse_args();sha=lambda b:hashlib.sha256(b).hexdigest();root=Path(__file__).resolve().parents[1]
lock=json.loads((root/'integration/sdr-startup/sources.json').read_text());elf=a.waterfall.read_bytes();assert sha(elf)==lock['waterfall_sha256']
raw=a.baseline.read_bytes();assert sha(raw)=='acdd13adf356e54433c35d135e56de868847d254321f88459b887ae58dd483df'
sys.path.insert(0,str(a.runtime/'scripts'));from spiffs_image import read_image;from paired_bank_images import initial_bank_state,parse_record
sys.path.insert(0,str(a.watch_product/'scripts'));import current_bootfs
store=read_image(raw[0x2f0000:0x840000],0x550000);before=dict(store);verify_springboard(store['springboard.elf'])
boot=json.loads(store['boot.json']);idx=next(i for i,x in enumerate(boot['app_capabilities']) if x['manifest']=='waterfall.json')
m,boot['app_capabilities'][idx]=provision(json.loads(store['waterfall.json']),boot['app_capabilities'][idx]);m['version']='0.3.5'
store['waterfall.json']=(json.dumps(m,sort_keys=True,separators=(',',':'))+'\n').encode();store['waterfall.elf']=elf
store['boot.json']=(json.dumps(boot,sort_keys=True,separators=(',',':'))+'\n').encode()
cohort=json.loads(store['cohort.json']);cohort['version']='0.1.27';cohort['source_revision']=subprocess.check_output(['git','-C',str(root),'rev-parse','HEAD'],text=True).strip();store['cohort.json']=(json.dumps(cohort,indent=2)+'\n').encode()
changed=sorted(n for n in store if store[n]!=before[n]);assert set(changed)=={'waterfall.elf','waterfall.json','boot.json','cohort.json'}
oldboot=json.loads(before['boot.json']);assert oldboot['drivers']==boot['drivers']
for row in oldboot['app_capabilities']:
 if row['manifest']!='waterfall.json':assert row in boot['app_capabilities']
assert boot['app_capabilities'][idx]['grants'][:len(oldboot['app_capabilities'][idx]['grants'])]==oldboot['app_capabilities'][idx]['grants']
fw=raw[0x10000:0x10000+cohort['firmware_size']];assert sha(fw)==cohort['firmware_sha256']
image,packing=current_bootfs.build(store,size=0x550000);assert read_image(image,0x550000)==store
state=initial_bank_state(fw,image,True,True);parse_record(state[:96],True,True)
full=bytearray(raw);full[0x2f0000:0x840000]=image;full[0xff2000:0xff2000+len(state)]=state
assert full[:0x2f0000]==raw[:0x2f0000] and full[0x840000:0xff2000]==raw[0x840000:0xff2000]
a.output.mkdir(parents=True,exist_ok=True)
for n,b in store.items():f=a.output/'waveshare-store'/n;f.parent.mkdir(parents=True,exist_ok=True);f.write_bytes(b)
name='Waveshare-0.1.27-sdr-startup-fixed-factory-erases-data-0x0.bin';(a.output/name).write_bytes(full)
proof={'version':'0.1.27','file':name,'bytes':len(full),'sha256':sha(full),'source_revision':cohort['source_revision'],'waterfall_sha256':sha(elf),'springboard_sha256':sha(store['springboard.elf']),'changed_store_files':changed,'packing':packing,'native_firmware_unchanged':True,'springboard_spectrum_home_and_other_apps_unchanged':True,'sd_contents_changed':False,'hardware_verified':False}
(a.output/'verification.json').write_text(json.dumps(proof,indent=2)+'\n');print(json.dumps(proof,indent=2))
