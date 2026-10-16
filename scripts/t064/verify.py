"""Full store admission with Waveshare's source-bound native composition.
Reuse the shared Watch harness with the source-bound exact namespace-1/6 writer registry.
"""
import argparse,hashlib,json,os,re,shutil,subprocess,sys,tempfile
from pathlib import Path
p=argparse.ArgumentParser()
for n in ['runtime','watch','store','output']:p.add_argument('--'+n,type=Path,required=True)
p.add_argument('--baseline-store',type=Path)
a=p.parse_args();a.runtime=a.runtime.resolve();a.watch=a.watch.resolve();a.output.mkdir(parents=True,exist_ok=True)
sys.path.insert(0,str(a.watch/'scripts'));import check_runtime_store_admission as m
native=(a.runtime/'.pio/build/waveshare-t051/firmware.elf').read_bytes();profile=a.runtime/'expanded-candidate.ini'
def composition(runtime,elf,selected,rows):
 assert Path(runtime)==a.runtime and Path(selected)==profile and rows==32
 head=subprocess.check_output(['git','-C',runtime,'rev-parse','HEAD'],text=True).strip()
 assert set(re.findall(rb'RTE_SOURCE=([^\x00\s]+)',elf))=={head.encode()}
 hashes={}
 for name in ['expanded-candidate.ini','waveshare-settings-profile.h','partitions-paired-appdata-expanded.csv','platformio.ini']:
  data=(runtime/name).read_bytes();assert data==subprocess.check_output(['git','-C',runtime,'show',head+':'+name]);hashes[name]=hashlib.sha256(data).hexdigest()
 bounds={'RISC_INSTALLED_APP_CAPACITY':64,'RISC_PROVIDER_CAPACITY':40,'RISC_APP_POLICY_ROWS':32,'RISC_APP_REQUIREMENT_ROWS':32}
 for key,value in bounds.items():assert '-D'+key+'='+str(value) in profile.read_text()
 for symbol,key in [('risc_app_policy_rows','RISC_APP_POLICY_ROWS'),('risc_app_requirement_rows','RISC_APP_REQUIREMENT_ROWS')]:assert m.native_symbol_bytes(elf,symbol)==(key+':32\0').encode()
 assert m.native_symbol_bytes(elf,'risc_usb_phy_resource_enabled')==b'\x01\0\0\0'
 for symbol in ['risc_sdmmc_host_abi','risc_tcp_listener_abi','risc_entropy_abi','risc_file_source_abi']:assert m.native_symbol_bytes(elf,symbol)==b'\x01\0\0\0'
 from verify_update_elf import verify_native_store_abi
 return dict(profile='env:waveshare-t051',runtime_commit=head,bounds=bounds,store_abi=3,file_source_enabled=True,store_size=0x550000,native_layout=verify_native_store_abi(elf,3),source_hashes=hashes)
m.native_composition=composition
commands=[];original_run=subprocess.run
def run(cmd,*args,**kw):
 if isinstance(cmd,list) and cmd and cmd[0]=='c++':cmd=[cmd[0],'-DRISC_RUNTIME_ATOMIC_KEY_VALUE=1','-include',str(a.runtime/'waveshare-settings-profile.h'),'-I'+str(a.runtime),'-Wno-unused-function','-Wno-unused-but-set-variable',*cmd[1:],'-Wno-unused-but-set-variable']
 commands.append([str(x) for x in cmd]);return original_run(cmd,*args,**kw)
with tempfile.TemporaryDirectory() as td:
 root=Path(td);(root/'tests').mkdir();shutil.copy(a.watch/'tests/app_data_admission_backend.h',root/'tests')
 s=(a.watch/'tests/runtime_store_admission.cpp').read_text();s='#include "waveshare-settings-profile.h"\n#include "experimental/native_replica/NativeAtomicKeyValue.h"\n'+s
 s=s.replace('bool bind(RiscBoot::Runtime& runtime) {','''using RC=RiscExperimental::NativeReplicaCore;
using AE=RiscExperimental::NativeAtomicKeyValue;
static RC core1(1,{}, {}, {}),core6(6,{}, {}, {});
static AE endpoint1(core1,{nullptr,[](void*){return true;},[](void*){++storageCalls;return false;},[](void*){++storageCalls;return false;},[](void*){++storageCalls;return false;},[](void*){++storageCalls;return -1;}});
static AE endpoint6(core6,{nullptr,[](void*){return true;},[](void*){++storageCalls;return false;},[](void*){++storageCalls;return false;},[](void*){++storageCalls;return false;},[](void*){++storageCalls;return -1;}});
bool bind(RiscBoot::Runtime& runtime) {
 struct Writer {const char *app;uint32_t ns;};
 static const Writer writers[]={RISC_NATIVE_SETTINGS_WRITERS};
 static_assert(sizeof(writers)/sizeof(writers[0])==23,"Exact T064 writer inventory changed");
 static_assert(RISC_NATIVE_SETTINGS_NAMESPACE_MASK==3,"Both namespaces must be selected");
 for(uint32_t ns:{1u,6u}) {
  if(!runtime.registerAtomicKeyValueReadThrough(ns,ns==1?endpoint1:endpoint6)||!runtime.registerKeyValueAvailability(ns,{nullptr,[](void*,uint32_t,risc_key_value_availability_state_v1*)->int32_t{++storageCalls;return RISC_KEY_VALUE_IO;}}))return false;
 }
 for(const auto&w:writers)if(!runtime.registerAtomicKeyValue(w.app,w.ns,w.ns==1?endpoint1:endpoint6))return false;
''')

 vendor=(Path(__file__).resolve().parents[2]/'native/VendorDisplay.cpp').read_text()
 assert vendor==(a.runtime/'src/VendorDisplay.cpp').read_text(), 'Staged native panel must match product source'
 accept=vendor[vendor.index('bool accepts('):vendor.index('void pads(')]
 s=s.replace('RiscCpu::Hardware hardware() {',accept+'\nRiscCpu::Hardware hardware() {')
 s=s.replace('  RiscCpu::Hardware h{};',"""  RiscCpu::Hardware h{};
 static RiscCpu::DisplayBackend display{accepts,[](const risc_hardware_device_v1&,uint8_t){++hardwareCalls;return false;},[](uint32_t,const uint16_t*,size_t){++hardwareCalls;return false;},[](uint8_t){++hardwareCalls;return false;},[](){++hardwareCalls;return false;}};
 h.displayBackend=&display;
 h.i2sStandardOpen=[](const risc_hw_i2s_standard_v1&,uint8_t,uint32_t){++hardwareCalls;return false;};
 static RiscStorage::Worker mailbox;
 static RiscCpu::StorageWorkBackend worker{&mailbox,[](){return true;},[](){return false;},[](uint32_t){++hardwareCalls;}};h.storageWork=&worker;
 h.sdmmcOpen=[](uint8_t,uint8_t,uint8_t,uint32_t,risc_sdmmc_card_info_v1*){++hardwareCalls;return false;};
 h.sdmmcRead=[](uint64_t,uint32_t,void*){++hardwareCalls;return false;};h.sdmmcWrite=[](uint64_t,uint32_t,const void*){++hardwareCalls;return false;};h.sdmmcSync=[](){++hardwareCalls;return false;};h.sdmmcClose=[](){++hardwareCalls;return false;};
""")
 (root/'tests/runtime_store_admission.cpp').write_text(s);m.ROOT=root;subprocess.run=run
 store={p.relative_to(a.store).as_posix():p.read_bytes() for p in a.store.rglob('*') if p.is_file()}
 active={p.relative_to(a.baseline_store).as_posix():p.read_bytes() for p in a.baseline_store.rglob('*') if p.is_file()} if a.baseline_store else store
 result=m.admit_cohort(a.runtime,native,active,store,app_policy_rows=32,native_profile=profile)
 subprocess.run=original_run
(a.output/'admission.json').write_text(json.dumps(dict(result=result,commands=commands),indent=2)+'\n');print(json.dumps(result,indent=2))
