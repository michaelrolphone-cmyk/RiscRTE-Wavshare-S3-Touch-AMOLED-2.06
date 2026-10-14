#!/usr/bin/env python3
"""Reduce restored shared Springboard raster cost while preserving SDR 0.1.27."""
import argparse,hashlib,json,subprocess,sys
from pathlib import Path
from shared_springboard_selection import verify as verify_springboard
p=argparse.ArgumentParser(description=__doc__)
for n in ('baseline','springboard','runtime','watch-product','output'):p.add_argument('--'+n,type=Path,required=True)
a=p.parse_args();sha=lambda b:hashlib.sha256(b).hexdigest();root=Path(__file__).resolve().parents[1]
lock=json.loads((root/'integration/springboard-drag/sources.json').read_text());elf=a.springboard.read_bytes();assert sha(elf)==lock['springboard_sha256']
raw=a.baseline.read_bytes();assert sha(raw)==lock['baseline_bin_sha256']
sys.path.insert(0,str(a.runtime/'scripts'));from spiffs_image import read_image;from paired_bank_images import initial_bank_state,parse_record
sys.path.insert(0,str(a.watch_product/'scripts'));import current_bootfs
store=read_image(raw[0x2f0000:0x840000],0x550000);before=dict(store);verify_springboard(elf)
m=json.loads(store['springboard.json']);m['version']=lock['springboard_version']
store['springboard.json']=(json.dumps(m,sort_keys=True,separators=(',',':'))+'\n').encode();store['springboard.elf']=elf
cohort=json.loads(store['cohort.json']);cohort['version']='0.1.28';cohort['source_revision']=subprocess.check_output(['git','-C',str(root),'rev-parse','HEAD'],text=True).strip();store['cohort.json']=(json.dumps(cohort,indent=2)+'\n').encode()
changed=sorted(n for n in store if store[n]!=before[n]);assert set(changed)=={'springboard.elf','springboard.json','cohort.json'}
assert store['waterfall.elf']==before['waterfall.elf'] and store['boot.json']==before['boot.json']
fw=raw[0x10000:0x10000+cohort['firmware_size']];assert sha(fw)==cohort['firmware_sha256']
image,packing=current_bootfs.build(store,size=0x550000);assert read_image(image,0x550000)==store
state=initial_bank_state(fw,image,True,True);parse_record(state[:96],True,True)
full=bytearray(raw);full[0x2f0000:0x840000]=image;full[0xff2000:0xff2000+len(state)]=state
assert full[:0x2f0000]==raw[:0x2f0000] and full[0x840000:0xff2000]==raw[0x840000:0xff2000]
a.output.mkdir(parents=True,exist_ok=True)
for n,b in store.items():f=a.output/'waveshare-store'/n;f.parent.mkdir(parents=True,exist_ok=True);f.write_bytes(b)
name='Waveshare-0.1.28-springboard-drag-factory-erases-data-0x0.bin';(a.output/name).write_bytes(full)
proof={'version':'0.1.28','file':name,'bytes':len(full),'sha256':sha(full),'source_revision':cohort['source_revision'],'springboard_sha256':sha(store['springboard.elf']),'changed_store_files':changed,'packing':packing,'native_firmware_unchanged':True,'waterfall_spectrum_home_and_other_apps_unchanged':True,'sd_contents_changed':False,'hardware_verified':False}
(a.output/'verification.json').write_text(json.dumps(proof,indent=2)+'\n');print(json.dumps(proof,indent=2))
