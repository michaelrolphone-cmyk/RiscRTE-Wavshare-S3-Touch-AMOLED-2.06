"""Assemble T051 initial provisioning image from the verified .29 baseline."""
from pathlib import Path
import argparse,hashlib,json,subprocess,sys
p=argparse.ArgumentParser()
for n in ['runtime','watch','baseline','store','output']:p.add_argument('--'+n,type=Path,required=True)
a=p.parse_args();r=Path(__file__).resolve().parents[1];rt=a.runtime.resolve();sys.path[:0]=[str(rt/'scripts'),str(a.watch.resolve()/'scripts')]
from spiffs_image import read_image
from paired_bank_images import initial_bank_state,parse_record
from verify_update_elf import verify_native_store_abi
import current_bootfs
sha=lambda b:hashlib.sha256(b).hexdigest()
raw=a.baseline.read_bytes();assert sha(raw)=='adefb0fee96cc4e474a881ba1b3ecfe9f01af381ad3fec95411bda5073b82591'
old=read_image(raw[0x2f0000:0x840000],0x550000)
store={p.relative_to(a.store).as_posix():p.read_bytes() for p in a.store.rglob('*') if p.is_file()}
assert set(store)==set(old)
changed={n for n in store if store[n]!=old[n]};assert changed=={'boot.json','wifi_settings.elf','wifi_settings.json','sd-volume/driver.elf','sd-volume/manifest.json'}
build=rt/'.pio/build/waveshare-t051';fw=(build/'firmware.bin').read_bytes();elf=(build/'firmware.elf').read_bytes();layout=verify_native_store_abi(elf,3)
head=subprocess.check_output(['git','-C',rt,'rev-parse','HEAD'],text=True).strip();product=subprocess.check_output(['git','-C',r,'rev-parse','HEAD'],text=True).strip()
assert ('RTE_SOURCE='+head+'\0').encode() in fw and len(fw)<=0x260000
assert raw[:len((build/'bootloader.bin').read_bytes())]==(build/'bootloader.bin').read_bytes()
assert raw[0x8000:0x8000+len((build/'partitions.bin').read_bytes())]==(build/'partitions.bin').read_bytes()
assert sha(raw[0x270000:0x2f0000])=='5f03c248f2de31c4da9ae8d9bc2033df064cee5e37694a9982f70fbb2f1d2ef0'
cohort=json.loads(store['cohort.json']);cohort.update(version='0.1.30',source_revision=product,firmware_size=len(fw),firmware_sha256=sha(fw));store['cohort.json']=(json.dumps(cohort,indent=2)+'\n').encode()
image,packing=current_bootfs.build(store,size=0x550000);assert read_image(image,0x550000)==store
state=initial_bank_state(fw,image,True,True);parse_record(state[:96],True,True)
full=bytearray(raw);full[0x10000:0x270000]=fw+b'\xff'*(0x260000-len(fw));full[0x2f0000:0x840000]=image;full[0xff2000:0xff2000+len(state)]=state
assert full[:0x10000]==raw[:0x10000] and full[0x270000:0x2f0000]==raw[0x270000:0x2f0000] and full[0x840000:0xff2000]==raw[0x840000:0xff2000]
a.output.mkdir(parents=True,exist_ok=True)
for n,b in store.items():f=a.output/'store'/n;f.parent.mkdir(parents=True,exist_ok=True);f.write_bytes(b)
name='Waveshare-0.1.30-T051-WiFi-factory-erases-data-0x0.bin';(a.output/name).write_bytes(full)
assert read_image((a.output/name).read_bytes()[0x2f0000:0x840000],0x550000)==store
proof=dict(status='assembled; final admission required',source_revision=product,runtime_source=head,file=name,sha256=sha(full),changed_files=sorted(changed|{'cohort.json'}),all_other_apps_unchanged=True,shared_keyboard=True,storage='native durable Wi-Fi namespace 6 with SD12 checkpoints',namespace_1_policy_unchanged=True,hardware_tested=False,packing=packing,native_layout=layout,inventory={n:sha(b) for n,b in store.items()})
(a.output/'verification.json').write_text(json.dumps(proof,indent=2)+'\n');print(name,proof['sha256'])
