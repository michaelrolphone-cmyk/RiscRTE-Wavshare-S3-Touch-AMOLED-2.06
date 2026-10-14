"""Assemble T030/T069 on exact T052 .31; workspace paths are explicit inputs."""
from pathlib import Path
import argparse,json,hashlib,subprocess,sys
p=argparse.ArgumentParser();p.add_argument('--workspace',type=Path,required=True);p.add_argument('--baseline-workspace',type=Path,required=True);a=p.parse_args();R=a.workspace;T=a.baseline_workspace;O=R/'t069-components'
sys.path[:0]=[str(T/'Runtime-wave-t051/scripts'),str(T/'TWatch-input-product/scripts')]
from spiffs_image import read_image
from paired_bank_images import initial_bank_state,parse_record
import current_bootfs
sha=lambda b:hashlib.sha256(b).hexdigest()
raw=(T/'t052-build/waveshare/Waveshare-0.1.31-T052-Mounted-Files-factory-erases-data-0x0.bin').read_bytes();assert sha(raw)=='678682400e084d02787077258d698b0c8ff11933ce595485f206b0a0e55ccd16'
size=0x550000;before=read_image(raw[0x2f0000:0x840000],size);store=dict(before)
for name,version in [('audio_spectrum','0.5.7'),('waterfall','0.3.6')]:
 b=(O/(name+'.elf')).read_bytes();assert sha(b)==json.loads((O/(name+'-build.json')).read_text())['sha256'];store[name+'.elf']=b
 m=json.loads(store[name+'.json']);m['version']=version;store[name+'.json']=(json.dumps(m,separators=(',',':'))+'\n').encode()
h=json.loads((T/'t030-build/handoff.json').read_text())
for n in ['springboard.elf','springboard.json']:
 b=(T/'t030-build'/n).read_bytes();assert sha(b)==h['files'][n]['sha256'];store[n]=b
head=subprocess.check_output(['git','-C',str(R/'wave-t069'),'rev-parse','HEAD'],text=True).strip();cohort=json.loads(store['cohort.json']);cohort.update(version='0.1.32',source_revision=head);store['cohort.json']=(json.dumps(cohort,indent=2)+'\n').encode()
changed=sorted(n for n in store if store[n]!=before[n]);assert changed==sorted(['cohort.json']+[n+ext for n in ['audio_spectrum','waterfall','springboard'] for ext in ['.elf','.json']])
fw=raw[0x10000:0x10000+cohort['firmware_size']];assert sha(fw)==cohort['firmware_sha256']
image,packing=current_bootfs.build(store,size=size);assert read_image(image,size)==store
state=initial_bank_state(fw,image,True,True);parse_record(state[:96],True,True)
full=bytearray(raw);full[0x2f0000:0x840000]=image;full[0xff2000:0xff2000+len(state)]=state
assert full[:0x2f0000]==raw[:0x2f0000] and full[0x840000:0xff2000]==raw[0x840000:0xff2000] and full[0xff2000+len(state):]==raw[0xff2000+len(state):]
name='Waveshare-0.1.32-T030-T069-factory-erases-data-0x0.bin';(O/name).write_bytes(full)
for n,b in store.items():q=O/'store'/n;q.parent.mkdir(parents=True,exist_ok=True);q.write_bytes(b)
proof=dict(file=name,version='0.1.32',sha256=sha(full),source_revision=head,changed_files=changed,native_unchanged=True,boot_grants_unchanged=True,all_other_apps_unchanged=True,packing=packing,hardware_verified=False,crash_reproduced=False,inventory={n:sha(b) for n,b in store.items()});(O/'verification.json').write_text(json.dumps(proof,indent=2)+'\n');print(name,proof['sha256'])
