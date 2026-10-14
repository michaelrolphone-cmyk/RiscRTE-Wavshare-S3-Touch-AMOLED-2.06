#!/usr/bin/env python3
"""Compose T054 from exact published T053 images; no device access."""
from pathlib import Path
import argparse,hashlib,json,subprocess,sys,shutil
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--product',choices=['wave','x4'],required=True)
for k in ('baseline','native-build','runtime','watch','shared','product-repo','output'):p.add_argument('--'+k,type=Path,required=True)
for k in ('components','home','settings','contexts','previous-sd'):p.add_argument('--'+k,type=Path)
a=p.parse_args();out=a.output;out.mkdir(parents=True,exist_ok=True)
sys.path[:0]=[str(a.runtime.resolve()/'scripts'),str(a.watch.resolve()/'scripts'),str(a.shared.resolve()/'scripts')]
from spiffs_image import read_image
from paired_bank_images import initial_bank_state,parse_record
from normalize_xtensa_relocations import normalize
from compact_current_elf import compact
import current_bootfs
sha=lambda b:hashlib.sha256(b).hexdigest();encode=lambda x:(json.dumps(x,separators=(',',':'))+'\n').encode()
wave=a.product=='wave';version='0.1.36' if wave else '0.1.119';previous='0.1.35' if wave else '0.1.118';size=0x550000 if wave else 0x510000
baseline_sha='485f6ba1ae4e36100a5e6ad857400fb0f8206d11d9f46cacc67fc7da7504bd25' if wave else 'f51d47e4a0b38a5969e4bf1af833537debe01d28a0d59a7cf7a1d39dfa71c72d'
raw=a.baseline.read_bytes();assert len(raw)==0x1000000 and sha(raw)==baseline_sha
for name,offset in [('bootloader.bin',0),('partitions.bin',0x8000)]:b=(a.native_build/name).read_bytes();assert b==raw[offset:offset+len(b)],name
before=read_image(raw[0x2f0000:0x2f0000+size],size);assert current_bootfs.build(before,size=size)[0]==raw[0x2f0000:0x2f0000+size]
store=dict(before);boot=json.loads(before['boot.json']);writers=[];changed_apps=[];absent=[]
if wave:
 assert all([a.components,a.home,a.settings,a.contexts])
 cc=str(Path.home()/'.platformio/packages/toolchain-xtensa-esp32s3/bin/xtensa-esp32s3-elf-gcc')
 for row in boot['app_capabilities']:
  if not any(g['capability']=='storage.key-value' and g['instance_id']==1 for g in row['grants']):continue
  m=json.loads(before[row['manifest']]);writers.append({'app':m['id'],'namespace':1});name=m['file_name']
  if name not in before:
   absent.append({'manifest':row['manifest'],'file':name,'remains_absent':True});continue
  source={'default.elf':a.home,'settings.elf':a.settings,'contexts.elf':a.contexts}.get(name,a.components/name)
  target=out/'compiled'/name;target.parent.mkdir(exist_ok=True);shutil.copyfile(source,target)
  if name in ('settings.elf','contexts.elf'):
   normalize(target);compact(target,cc,debug_path=out/'debug'/name)
  data=target.read_bytes();assert b'storage.key-value.atomic\0' in data,name
  store[name]=data;v=m['version'].split('.');v[-1]=str(int(v[-1])+1);m['version']='.'.join(v)
  required={'capability':'storage.key-value.atomic','api':1}
  if required not in m['requires']:m['requires'].append(required)
  grant={**required,'instance_id':1}
  if grant not in row['grants']:row['grants'].append(grant)
  store[row['manifest']]=encode(m);changed_apps.append({'manifest':row['manifest'],'id':m['id'],'version':m['version'],'sha256':sha(data),'source':str(source.resolve())})
 writers.append({'app':'wifi_settings','namespace':6});store['boot.json']=encode(boot)
fw=(a.native_build/'firmware.bin').read_bytes();assert len(fw)<=0x260000
runtime_head=subprocess.check_output(['git','-C',a.runtime,'rev-parse','HEAD'],text=True).strip();assert ('RTE_SOURCE='+runtime_head+'\0').encode() in fw
product_head=subprocess.check_output(['git','-C',a.product_repo,'rev-parse','HEAD'],text=True).strip()
cohort=json.loads(before['cohort.json']);assert cohort['version']==previous;cohort.update(version=version,source_revision=product_head,firmware_size=len(fw),firmware_sha256=sha(fw));store['cohort.json']=encode(cohort)
image,packing=current_bootfs.build(store,size=size);assert read_image(image,size)==store
state=initial_bank_state(fw,image,True,True) if wave else initial_bank_state(fw,image,True)
parse_record(state[:96],True,True) if wave else parse_record(state[:96],True)
full=bytearray(raw);full[0x10000:0x270000]=fw+b'\xff'*(0x260000-len(fw));full[0x2f0000:0x2f0000+size]=image;full[0xff2000:0xff2000+len(state)]=state
for lo,hi in [(0,0x10000),(0x270000,0x2f0000),(0x2f0000+size,0xff2000),(0xff3000,len(full))]:assert full[lo:hi]==raw[lo:hi]
name=('Waveshare' if wave else 'X4')+'-'+version+'-T054-Preferences-factory-erases-data-0x0.bin';(out/name).write_bytes(full)
for n,b in store.items():q=out/'store'/n;q.parent.mkdir(parents=True,exist_ok=True);q.write_bytes(b)
changed=sorted(n for n in store if before[n]!=store[n]);allowed={'cohort.json'}|({'boot.json'}|{r['manifest'] for r in changed_apps}|{json.loads(store[r['manifest']])['file_name'] for r in changed_apps} if wave else set());assert set(changed)==allowed
proof={'file':name,'version':version,'image_sha256':sha(full),'baseline_sha256':baseline_sha,'runtime_commit':runtime_head,'product_commit':product_head,'native_sha256':sha(fw),'native_bytes':len(fw),'bootloader_partitions_unchanged':True,'settings_partitions_unchanged':True,'all_other_store_files_unchanged':True,'changed_store_files':changed,'changed_apps':changed_apps,'exact_writers':writers,'unavailable_apps_preserved':absent,'packing':packing,'hardware_tested':False,'inventory':{n:sha(b) for n,b in store.items()}}
if not wave:
 assert a.previous_sd and sha(a.previous_sd.read_bytes())=='e25e58bf028aa50a8b3287987c326e48ee3f2723df2d6686e60c3533c1157d2a'
 sdname='X4-'+version+'-Cumulative-Changed-SD-Keep-Existing.zip';shutil.copyfile(a.previous_sd,out/sdname);proof.update(sd_file=sdname,sd_sha256=sha((out/sdname).read_bytes()),all_sd_bytes_unchanged=True,all_application_bytes_unchanged=True)
(out/'assembly-report.json').write_text(json.dumps(proof,indent=2)+'\n');print(name,proof['image_sha256'],packing)
