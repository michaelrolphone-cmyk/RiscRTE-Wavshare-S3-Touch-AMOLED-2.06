#!/usr/bin/env python3
"""Assemble an offline initial bank0 image; never connect to a device."""
import argparse,hashlib,json,re,shutil,subprocess,sys,struct,zlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def sha(b):return hashlib.sha256(b).hexdigest()
def write(p,v):p.write_text(json.dumps(v,indent=2)+'\n')
def main():
 p=argparse.ArgumentParser(description=__doc__)
 for k in ('runtime','native','store','appdata','packer','readback-packer','output'):p.add_argument('--'+k,type=Path,required=True)
 p.add_argument('--expanded',action='store_true',help='Explicit ABI3 stores and relocated bank1; incompatible full provisioning')
 a=p.parse_args()
 store_size=0x550000 if a.expanded else 0x510000
 abi=3 if a.expanded else 2
 target='esp32s3-16mb-waveshare-expanded' if a.expanded else 'esp32s3-16mb-waveshare-appdata'
 version='0.1.15' if a.expanded else '0.1.14'
 for k,v in vars(a).items():
  if isinstance(v,Path):setattr(a,k,v.resolve())
 if a.output.exists():raise ValueError('New output directory required')
 sys.path.insert(0,str(a.runtime/'scripts'))
 from paired_candidate import partitions,APP_DATA_EXPECTED,APP_DATA_EXPANDED_EXPECTED,native_proof
 from paired_bank_images import initial_bank_state,initial_otadata,parse_record,BOOTLOADER_SHA256
 from app_data_image import verify_initial
 from spiffs_image import read_image
 from store_image_capacity import inspect
 from release_assets import esp_image
 from radio_iq_proof import prove
 native={n:(a.native/n).read_bytes() for n in ('firmware.bin','firmware.elf','bootloader.bin','partitions.bin')}
 layout=partitions(native['partitions.bin'],APP_DATA_EXPANDED_EXPECTED if a.expanded else APP_DATA_EXPECTED);proof=native_proof(native['firmware.elf']);proof['radio_iq']=prove(native['firmware.elf'],target_identity=target)
 runtime_sha=subprocess.check_output(['git','-C',str(a.runtime),'rev-parse','HEAD'],text=True).strip()
 device_sha=subprocess.check_output(['git','-C',str(ROOT),'rev-parse','HEAD'],text=True).strip()
 for repo in (a.runtime,ROOT):assert not subprocess.check_output(['git','-C',str(repo),'diff','HEAD','--name-only'],text=True).strip()
 for name in ('firmware.bin','firmware.elf'):
  for marker in ('RTE_SOURCE='+runtime_sha,'RISC_PAIRED_STORE_ABI:'+str(abi),'RISC_APP_POLICY_ROWS:32','RISC_APP_REQUIREMENT_ROWS:32',target):assert marker.encode()+b'\0' in native[name],marker
 assert sha(native['bootloader.bin'])==BOOTLOADER_SHA256
 for name in ('firmware.bin','bootloader.bin'):esp_image(native[name]);assert native[name][3]>>4==4
 assert len(native['firmware.bin'])<=0x260000
 runtime_version=re.findall(rb'RISC_RUNTIME_VERSION:([^\x00]+)',native['firmware.bin']);assert len(runtime_version)==1
 appdata=verify_initial(a.appdata)
 identity={'schema':'riscrte.cohort','schema_version':1,'product':'waveshare-s3-touch-amoled-206','version':version,'runtime_version':runtime_version[0].decode(),'source_repo':'michaelrolphone-cmyk/RiscRTE-Wavshare-S3-Touch-AMOLED-2.06','source_revision':device_sha,'layout':'riscrte-paired-appdata-v3' if a.expanded else 'riscrte-paired-appdata-v2','store_abi':abi,'firmware_size':len(native['firmware.bin']),'firmware_sha256':sha(native['firmware.bin'])}
 a.output.mkdir();store=a.output/'store';shutil.copytree(a.store,store)
 assert not (store/'cohort.json').exists();write(store/'cohort.json',identity)
 image=a.output/'bootfs0.bin'
 subprocess.run([str(a.packer),'-c',str(store),'-b','4096','-p','256','-s',str(store_size),str(image)],check=True,stdout=subprocess.DEVNULL)
 bootfs=image.read_bytes();expected={str(f.relative_to(store)):f.read_bytes() for f in store.rglob('*') if f.is_file()}
 assert read_image(bootfs,store_size)==expected
 occupancy=inspect(bootfs)
 readback=a.output/'readback';readback.mkdir()
 subprocess.run([str(a.readback_packer),'-u',str(readback),'-b','4096','-p','256','-s',str(store_size),str(image)],check=True,stdout=subprocess.DEVNULL)
 assert {str(f.relative_to(readback)):f.read_bytes() for f in readback.rglob('*') if f.is_file()}==expected
 state=initial_bank_state(native['firmware.bin'],bootfs,True,a.expanded);fields=parse_record(state[:96],True,a.expanded)
 assert fields[2]==0 and fields[3]==len(native['firmware.bin']) and fields[6]==hashlib.sha256(native['firmware.bin']).digest() and fields[7]==hashlib.sha256(bootfs).digest()
 ota=initial_otadata();seq=struct.unpack_from('<I',ota)[0];assert seq==1 and struct.unpack_from('<I',ota,28)[0]==zlib.crc32(ota[:4],0xffffffff)&0xffffffff
 segments={'bootloader.bin':(0,native['bootloader.bin']),'partitions.bin':(0x8000,native['partitions.bin']),'firmware.bin':(0x10000,native['firmware.bin']),'appdata.bin':(0x270000,(a.appdata/'appdata.bin').read_bytes()),'bootfs0.bin':(0x2f0000,bootfs),'otadata.bin':(0xff0000,ota),'bank_state.bin':(0xff2000,state)}
 full=bytearray(b'\xff'*0x1000000);last=0
 for name,(offset,data) in sorted(segments.items(),key=lambda x:x[1][0]):
  assert offset>=last and offset+len(data)<=len(full);full[offset:offset+len(data)]=data;last=offset+len(data);(a.output/name).write_bytes(data)
 for name in ('nvs','app1','bootfs1'):
  _,_,offset,size=layout[name];assert full[offset:offset+size]==b'\xff'*size
 path=a.output/('Waveshare-0.1.15-expanded-updates-full-initial-erases-data-0x0.bin' if a.expanded else 'Waveshare-0.1.14-canonical-contexts-full-initial-erases-data-0x0.bin');path.write_bytes(full);reopened=path.read_bytes();assert reopened==full
 for name,(offset,data) in segments.items():assert reopened[offset:offset+len(data)]==data
 assert read_image(reopened[0x2f0000:0x2f0000+store_size],store_size)==expected
 assert parse_record(reopened[0xff2000:0xff2060],True,a.expanded)==fields
 (a.output/'firmware.elf').write_bytes(native['firmware.elf']);shutil.copy2(a.appdata/'appdata-image.json',a.output/'appdata-image.json')
 write(a.output/'assembly.json',{'schema':1,'runtime_source':runtime_sha,'device_source':device_sha,'cohort':identity,'native_proof':proof,'partitions':layout,'initial_appdata':appdata,'physical_capacity':occupancy,'store_files':{n:{'bytes':len(b),'sha256':sha(b)} for n,b in expected.items()},'segments':{n:{'offset':o,'bytes':len(b),'sha256':sha(b)} for n,(o,b) in segments.items()},'image':{'filename':path.name,'bytes':len(full),'sha256':sha(full),'write_address':0},'bank0':'valid exact firmware/store binding','bank1':'blank','independent_and_original_readback':True,'cohort_runtime_validation':'pending','hardware_verified':False,'release_ready':False,'scope':'Offline initial-install candidate; full image erases NVS/app-data if used. Not a data-preserving update. No device operation.'})
 print(path)
if __name__=='__main__':main()
