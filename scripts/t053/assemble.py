#!/usr/bin/env python3
"""Compose T053 on verified T039; preserve every unrelated byte/file."""
from pathlib import Path
import argparse,hashlib,json,subprocess,sys,zipfile
p=argparse.ArgumentParser()
for n in ('baseline','app','msc','runtime','watch','product-repo','output'):p.add_argument('--'+n,type=Path,required=True)
p.add_argument('--product',choices=['wave','x4'],required=True);p.add_argument('--sd',type=Path);p.add_argument('--previous-sd',type=Path);a=p.parse_args()
sys.path[:0]=[str(a.runtime.resolve()/'scripts'),str(a.watch.resolve()/'scripts')]
from spiffs_image import read_image
from paired_bank_images import initial_bank_state,parse_record
import current_bootfs
sha=lambda b:hashlib.sha256(b).hexdigest();enc=lambda o:(json.dumps(o,separators=(',',':'))+'\n').encode()
wave=a.product=='wave';version='0.1.35' if wave else '0.1.118';oldversion='0.1.34' if wave else '0.1.117';name='Waveshare' if wave else 'X4';size=0x550000 if wave else 0x510000
raw=a.baseline.read_bytes();assert sha(raw)==('b0206707a89143f926519ec32923fb1182e494a0c2c1d61ab4d41503aa0d87b2' if wave else 'b310264f8951e2a84dc384a84e9df309fe642172f9f8baa4f450d914bbe59d86')
before=read_image(raw[0x2f0000:0x2f0000+size],size);assert current_bootfs.build(before,size=size)[0]==raw[0x2f0000:0x2f0000+size];store=dict(before)
for f in ('usb_sd_transfer.elf','usb_sd_transfer.json'):store[f]=(a.app/f).read_bytes()
for f in ('driver.elf','manifest.json'):store['usb-msc/'+f]=(a.msc/f).read_bytes()
assert json.loads(store['usb_sd_transfer.json'])['version']=='0.1.11' and json.loads(store['usb-msc/manifest.json'])['version']=='0.1.8'
boot=json.loads(before['boot.json']);mscsha=sha(store['usb-msc/driver.elf'])
if wave:
 assert a.sd;boot['drivers'].append({'manifest':'usb-msc/manifest.json'})
 boot['app_capabilities'].append({'manifest':'usb_sd_transfer.json','grants':[{'capability':c,'api':1,'instance_id':i} for c,i in [('display.output',5),('input.touch.raw',6),('usb.device.msc',0)]]})
 for f in ('driver.elf','manifest.json'):store['sd-volume/'+f]=(a.sd/f).read_bytes()
 assert json.loads(store['sd-volume/manifest.json'])['version']=='0.2.1'
else:
 row=next(x for x in boot['drivers'] if x['manifest']=='usb-msc/manifest.json');row['image_source']['path']=f'Drivers/usb-device-msc-esp32s3/image-{mscsha}.elf'
store['boot.json']=enc(boot);cohort=json.loads(before['cohort.json']);assert cohort['version']==oldversion
source=subprocess.check_output(['git','-C',str(a.product_repo),'rev-parse','HEAD'],text=True).strip();cohort.update(version=version,source_revision=source)
fw=raw[0x10000:0x10000+cohort['firmware_size']];assert sha(fw)==cohort['firmware_sha256']
if wave:
 build=a.runtime/'.pio/build/waveshare-t051';fw=(build/'firmware.bin').read_bytes();head=subprocess.check_output(['git','-C',str(a.runtime),'rev-parse','HEAD'],text=True).strip();assert ('RTE_SOURCE='+head+'\0').encode() in fw and len(fw)<=0x260000
 for f,offset in [('bootloader.bin',0),('partitions.bin',0x8000)]:b=(build/f).read_bytes();assert raw[offset:offset+len(b)]==b
 cohort.update(firmware_size=len(fw),firmware_sha256=sha(fw))
store['cohort.json']=enc(cohort);expected={'boot.json','cohort.json','usb_sd_transfer.elf','usb_sd_transfer.json','usb-msc/driver.elf','usb-msc/manifest.json'}|({'sd-volume/driver.elf','sd-volume/manifest.json'} if wave else set())
changed={n for n,b in store.items() if before.get(n)!=b};assert changed==expected
image,packing=current_bootfs.build(store,size=size);assert current_bootfs.build(store,size=size)[0]==image and read_image(image,size)==store
state=initial_bank_state(fw,image,True,True) if wave else initial_bank_state(fw,image,True);parse_record(state[:96],True,True) if wave else parse_record(state[:96],True)
full=bytearray(raw);full[0x10000:0x270000]=fw+b'\xff'*(0x260000-len(fw)) if wave else raw[0x10000:0x270000];full[0x2f0000:0x2f0000+size]=image;full[0xff2000:0xff2000+len(state)]=state
assert full[:0x10000]==raw[:0x10000] and full[0x270000:0x2f0000]==raw[0x270000:0x2f0000] and full[0x2f0000+size:0xff2000]==raw[0x2f0000+size:0xff2000] and full[0xff3000:]==raw[0xff3000:]
out=a.output;out.mkdir(parents=True,exist_ok=True);filename=f'{name}-{version}-T053-USB-Storage-factory-erases-data-0x0.bin';(out/filename).write_bytes(full)
for n,b in store.items():f=out/'store'/n;f.parent.mkdir(parents=True,exist_ok=True);f.write_bytes(b)
proof=dict(file=filename,version=version,image_sha256=sha(full),baseline_sha256=sha(raw),source_revision=source,changed_store_files=sorted(changed),native_unchanged=not wave,home_unchanged=store['default.elf']==before['default.elf'],settings_partitions_unchanged=True,packing=packing,hardware_tested=False,inventory={n:sha(b) for n,b in store.items()})
if not wave:
 assert a.previous_sd and sha(a.previous_sd.read_bytes())=='9285fa99070a3a8e47e3b2018188636436b2a028db0f8ae6b8df82650171678e'
 with zipfile.ZipFile(a.previous_sd) as z:old={n:z.read(n) for n in z.namelist() if not n.endswith('/')}
 sd=dict(old);path=next(x for x in boot['drivers'] if x['manifest']=='usb-msc/manifest.json')['image_source']['path'];sd[path]=store['usb-msc/driver.elf'];sd['Drivers/usb-device-msc-esp32s3/manifest.json']=store['usb-msc/manifest.json'];sdname=f'X4-{version}-Cumulative-Changed-SD-Keep-Existing.zip'
 with zipfile.ZipFile(out/sdname,'w',zipfile.ZIP_DEFLATED) as z:
  for n,b in sorted(sd.items()):item=zipfile.ZipInfo(n,(2026,10,14,0,0,0));item.compress_type=zipfile.ZIP_DEFLATED;z.writestr(item,b)
 assert all(sd[n]==b for n,b in old.items() if n!='Drivers/usb-device-msc-esp32s3/manifest.json')
 proof.update(sd_file=sdname,sd_sha256=sha((out/sdname).read_bytes()),sd_inventory={n:sha(b) for n,b in sd.items()},other_sd_files_unchanged=True)
(out/'assembly-report.json').write_text(json.dumps(proof,indent=2)+'\n');print(name,version,sha(full),packing)
