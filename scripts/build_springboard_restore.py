#!/usr/bin/env python3
"""Restore the verified shared Springboard, preserving the combined firmware."""
import argparse,hashlib,json,subprocess,sys
from pathlib import Path
from shared_springboard_selection import verify,SOURCE_REVISION,ELF_SHA256
p=argparse.ArgumentParser(description=__doc__)
for n in ('combined','working','launcher','runtime','watch-product','output'):p.add_argument('--'+n,type=Path,required=True)
a=p.parse_args();sha=lambda b:hashlib.sha256(b).hexdigest()
sys.path.insert(0,str(a.runtime/'scripts'));from spiffs_image import read_image;from paired_bank_images import initial_bank_state,parse_record
sys.path.insert(0,str(a.watch_product/'scripts'));import current_bootfs
raw=a.combined.read_bytes();old=a.working.read_bytes()
assert sha(raw)=='2c8bf3a436d69440937f4747b0633eab9fc5ac217427797c142710163f21c11f'
assert sha(old)=='79af497a35f9d1d1c512c6481f223bd285ac77e7f7cb41a7b7bdc446df2d7f77'
store=read_image(raw[0x2f0000:0x840000],0x550000);before=dict(store);working=read_image(old[0x2f0000:0x840000],0x550000)
launcher=verify(a.launcher.read_bytes());assert launcher==verify(working['springboard.elf'])
store['springboard.elf']=launcher;store['springboard.json']=working['springboard.json']
boot=json.loads(store['boot.json']);oldboot=json.loads(working['boot.json'])
row=next(x for x in oldboot['app_capabilities'] if x['manifest']=='springboard.json');assert 'image_source' not in row
boot['app_capabilities']=[row if x['manifest']=='springboard.json' else x for x in boot['app_capabilities']]
assert boot['default_app']==oldboot['default_app']=='default.elf'
store['boot.json']=(json.dumps(boot,sort_keys=True,separators=(',',':'))+'\n').encode()
cohort=json.loads(store['cohort.json']);cohort['version']='0.1.26';cohort['source_revision']=subprocess.check_output(['git','-C',str(Path(__file__).resolve().parents[1]),'rev-parse','HEAD'],text=True).strip()
store['cohort.json']=(json.dumps(cohort,indent=2)+'\n').encode()
changed=sorted(n for n in store if store[n]!=before[n]);assert set(changed)=={'springboard.elf','springboard.json','boot.json','cohort.json'}
assert boot['drivers']==json.loads(before['boot.json'])['drivers']
for r in json.loads(before['boot.json'])['app_capabilities']:
 if r['manifest']!='springboard.json':assert r in boot['app_capabilities']
fw=raw[0x10000:0x10000+cohort['firmware_size']];assert sha(fw)==cohort['firmware_sha256']
image,packing=current_bootfs.build(store,size=0x550000);assert read_image(image,0x550000)==store
state=initial_bank_state(fw,image,True,True);parse_record(state[:96],True,True)
full=bytearray(raw);full[0x2f0000:0x840000]=image;full[0xff2000:0xff2000+len(state)]=state
assert full[:0x2f0000]==raw[:0x2f0000] and full[0x840000:0xff2000]==raw[0x840000:0xff2000]
a.output.mkdir(parents=True,exist_ok=True)
for n,b in store.items():f=a.output/'waveshare-store'/n;f.parent.mkdir(parents=True,exist_ok=True);f.write_bytes(b)
name='Waveshare-0.1.26-restored-shared-springboard-factory-erases-data-0x0.bin';(a.output/name).write_bytes(full)
proof={'file':name,'version':'0.1.26','bytes':len(full),'sha256':sha(full),'product_revision':cohort['source_revision'],'springboard_source':SOURCE_REVISION,'springboard_sha256':ELF_SHA256,'springboard_bytes':len(launcher),'replaced_springboard_sha256':sha(before['springboard.elf']),'changed_store_files':changed,'packing':packing,'native_firmware_unchanged':True,'spectrum_and_all_other_apps_unchanged':True,'native_display_410x502_preserved':True,'sd_contents_changed':False,'launch_path':'default.elf request_launch("springboard.elf") -> internal springboard.json -> springboard.elf app_main -> clock.elf -> fresh default.elf','hardware_verified':False}
(a.output/'verification.json').write_text(json.dumps(proof,indent=2)+'\n');print(json.dumps(proof,indent=2))
