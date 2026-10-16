"""Compose only Home and its explicit grants over each exact cumulative baseline."""
from pathlib import Path
import sys,json,hashlib,subprocess,argparse
p=argparse.ArgumentParser();p.add_argument('device',choices=['x4','wave','watch']);a=p.parse_args();root=Path.cwd();sys.path[:0]=[str(root/'Runtime-wave-t054/scripts'),str(root/'Watch-t054/scripts')]
from spiffs_image import read_image
from paired_bank_images import initial_bank_state,parse_record
import current_bootfs
sha=lambda b:hashlib.sha256(b).hexdigest();enc=lambda d:(json.dumps(d,separators=(',',':'))+'\n').encode()
config={'wave':('t064-build/wave','464079ea8735175e7042ada02ede02f9bffe281791aa9f2dd6c62c666f5f1422','0.1.38','0.1.39','Waveshare','Wave-custody',0x550000,'wave-custody-build/springboard')}
folder,expected,old,new,label,repo,size,home=config[a.device];baseline=next((root/folder).glob('*factory*bin'));raw=baseline.read_bytes();assert sha(raw)==expected
before=read_image(raw[0x2f0000:0x2f0000+size],size);store=dict(before);h=root/home
store['springboard.elf']=(h/'springboard.elf').read_bytes();store['springboard.json']=(h/'springboard.json').read_bytes()
cohort=json.loads(before['cohort.json']);assert cohort['version']==old;cohort['version']=new;cohort['source_revision']=subprocess.check_output(['git','-C',repo,'rev-parse','HEAD'],text=True).strip();store['cohort.json']=enc(cohort)
image,packing=current_bootfs.build(store,size=size);assert read_image(image,size)==store
fw=raw[0x10000:0x10000+cohort['firmware_size']];assert sha(fw)==cohort['firmware_sha256'];state=initial_bank_state(fw,image,True,a.device!='x4');parse_record(state[:96],True,a.device!='x4')
full=bytearray(raw);full[0x2f0000:0x2f0000+size]=image;full[0xff2000:0xff2000+len(state)]=state
assert full[:0x2f0000]==raw[:0x2f0000] and full[0x2f0000+size:0xff2000]==raw[0x2f0000+size:0xff2000] and full[0xff3000:]==raw[0xff3000:]
changed=sorted(k for k in store if store[k]!=before[k]);assert changed==sorted(['springboard.elf','springboard.json','cohort.json'])
out=root/'wave-custody-build/release';out.mkdir(parents=True,exist_ok=True);name=f'{label}-{new}-Catalog-Display-Fix-factory-erases-data-0x0.bin';(out/name).write_bytes(full)
for k,v in store.items():p=out/'store'/k;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(v)
proof=dict(file=name,version=new,image_sha256=sha(full),baseline_sha256=expected,baseline_file=str(baseline),native_sha256=sha(fw),native_unchanged=True,all_other_store_files_unchanged=True,changed_store_files=changed,packing=packing,crash_namespace=62 if a.device=='x4' else 61,crash_sd_instance={'x4':9,'wave':12,'watch':None}[a.device],hardware_tested=False)
if a.device=='x4':
 sd=next((root/folder).glob('*Changed-SD*.zip'));proof.update(sd_file=str(sd),sd_sha256=sha(sd.read_bytes()),sd_unchanged=True)
(out/'assembly-report.json').write_text(json.dumps(proof,indent=2)+'\n');print(name,sha(full),packing['empty_blocks'])
