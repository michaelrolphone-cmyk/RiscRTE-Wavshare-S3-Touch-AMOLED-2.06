#!/usr/bin/env python3
"""Assemble a diagnostic-only Springboard over exact Waveshare 0.1.39.

No device access. Changes only Springboard ELF/manifest and cohort metadata.
"""
import argparse,hashlib,json,subprocess,sys
from pathlib import Path
BASELINE_SHA='93531640691a0a1b3b6718e01aeca388fe3cbe6c5e4f9f396ff262d0c166fa35'
VERSION='0.1.41'
sha=lambda b:hashlib.sha256(b).hexdigest()
enc=lambda value:(json.dumps(value,separators=(',',':'))+'\n').encode()
def main():
 p=argparse.ArgumentParser(description=__doc__)
 for key in ('baseline','springboard','runtime','image-helper','output'):p.add_argument('--'+key,type=Path,required=True)
 p.add_argument('--source-revision',required=True);p.add_argument('--system-revision',required=True)
 a=p.parse_args();sys.path[:0]=[str(a.runtime.resolve()/'scripts'),str(a.image_helper.resolve()/'scripts')]
 from spiffs_image import read_image
 from paired_bank_images import initial_bank_state,parse_record
 import current_bootfs
 raw=a.baseline.read_bytes();assert len(raw)==0x1000000 and sha(raw)==BASELINE_SHA
 size=0x550000;before=read_image(raw[0x2f0000:0x2f0000+size],size);store=dict(before)
 cohort=json.loads(before['cohort.json']);assert cohort['version']=='0.1.39'
 store['springboard.elf']=a.springboard.read_bytes()
 manifest=json.loads(before['springboard.json']);manifest['version']='1.7.16';store['springboard.json']=enc(manifest)
 cohort['version']=VERSION;cohort['source_revision']=a.source_revision;store['cohort.json']=enc(cohort)
 changed=sorted(k for k in store if store[k]!=before[k]);assert changed==['cohort.json','springboard.elf','springboard.json']
 image,packing=current_bootfs.build(store,size=size);assert read_image(image,size)==store
 firmware=raw[0x10000:0x10000+cohort['firmware_size']];assert sha(firmware)==cohort['firmware_sha256']
 state=initial_bank_state(firmware,image,True,True);parse_record(state[:96],True,True)
 full=bytearray(raw);full[0x2f0000:0x2f0000+size]=image;full[0xff2000:0xff2000+len(state)]=state
 assert full[:0x2f0000]==raw[:0x2f0000] and full[0x2f0000+size:0xff2000]==raw[0x2f0000+size:0xff2000] and full[0xff3000:]==raw[0xff3000:]
 a.output.mkdir(parents=True,exist_ok=True);name=f'Waveshare-{VERSION}-Catalog-Diagnostic-factory-erases-data-0x0.bin'
 (a.output/name).write_bytes(full)
 for name2,value in store.items():q=a.output/'store'/name2;q.parent.mkdir(parents=True,exist_ok=True);q.write_bytes(value)
 report={'version':VERSION,'diagnostic_only':True,'physical_root_cause_verified':False,'hardware_tested':False,'device_accessed':False,'file':name,'image_sha256':sha(full),'baseline_version':'0.1.39','baseline_sha256':BASELINE_SHA,'source_revision':a.source_revision,'system_revision':a.system_revision,'native_revision':'c258c4ba144247b6eaa4c6f28675ffccec582fe1','native_unchanged':True,'native_sha256':sha(firmware),'springboard_sha256':sha(store['springboard.elf']),'all_other_store_files_unchanged':True,'changed_store_files':changed,'packing':packing,'factory_erases_saved_data':True,'sd_unchanged':True}
 (a.output/'assembly-report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
if __name__=='__main__':main()
