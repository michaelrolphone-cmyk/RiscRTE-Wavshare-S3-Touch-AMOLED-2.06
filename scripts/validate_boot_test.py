#!/usr/bin/env python3
"""Validate a complete boot store without performing hardware or storage I/O."""
from pathlib import Path
import subprocess,sys,os,argparse
p=argparse.ArgumentParser(description=__doc__)
for name in ('runtime','controllers','native-elf','store','output'):p.add_argument('--'+name,required=True,type=Path)
p.add_argument('--sanitize',action='store_true')
p.add_argument('--cohort-store',type=Path,help='Validate this candidate against the admitted --store cohort')
p.add_argument('--app-data',action='store_true',help='Successor admission with explicit app-data backend; no storage calls allowed')
args=p.parse_args()
N=args.runtime.resolve();T=args.controllers.resolve();out=args.output.resolve();out.mkdir(parents=True,exist_ok=True)
sys.path.insert(0,str(T/'scripts'))
from verify_update_elf import cohort_admission_header
(out/'cohort_elf_admission.h').write_text('#pragma once\n'+cohort_admission_header(N,args.native_elf.read_bytes()))
s=(T/'tests/runtime_store_admission.cpp').read_text()
s=s.replace('#include <cstdio>','#include <cstdio>\n#include "cohort_elf_admission.h"')
s=s.replace('  RiscCpu::Hardware h{};','''  RiscCpu::Hardware h{};
  static const RiscCpu::DisplayBackend displayBackend={
    [](const risc_hardware_device_v1&,uint8_t){return true;},
    [](const risc_hardware_device_v1&,uint8_t){++hardwareCalls;return false;},
    [](uint32_t,const uint16_t*,size_t){++hardwareCalls;return false;},
    [](uint8_t){++hardwareCalls;return false;},
    [](){++hardwareCalls;return false;}};
  h.displayBackend=&displayBackend;
  h.i2sStandardOpen=[](const risc_hw_i2s_standard_v1&,uint8_t,uint32_t){++hardwareCalls;return false;};
  h.spiOpenQuad=[](uint8_t,int16_t,int16_t,int16_t,int16_t,int16_t){++hardwareCalls;return false;};
  h.spiTransferFrame=[](uint8_t,const risc_spi_frame_v1*,const uint8_t*,size_t,uint32_t){++hardwareCalls;return false;};
  h.spiTransferQuad=[](uint8_t,const uint8_t*,size_t,uint32_t){++hardwareCalls;return false;};''')
a=s.index('  // Runtime errors are constant diagnostics');b=s.index('#endif\n  return hardwareCalls',a)
s=s[:a]+'''  unsigned admitted=0;
  const bool inspected=prepared && runtime.inspectImages(CohortElf::file,&admitted);
  printf("{\\"prepared\\":%s,\\"images_validated\\":%s,\\"error\\":\\"%s\\",\\"hardware_calls\\":%u,\\"storage_calls\\":%u,\\"elf_count\\":%u}\\n",
         prepared?"true":"false",inspected?"true":"false",runtime.error(),hardwareCalls,storageCalls,admitted);
  if(!prepared || !inspected)return 4;
'''+s[b:]
s=s.replace('prepared?candidate.error():runtime.error(),hardwareCalls,storageCalls,admitted,cooperativeYields);', 'prepared?candidate.error():runtime.error(),hardwareCalls,storageCalls,admitted,cooperativeYields);\n  if(!prepared || !validated)return 4;')
(out/'admission.cpp').write_text(s)
incs=[N/p for p in ['src','sdk/app','sdk/driver','sdk/hardware','lib/ArduinoJson/src','test/drivers/stubs','lib/elf_loader/include','test/native_bank_stubs']]+[out,T/'tests']
flags=['-std=c++17','-Wall','-Wextra','-Werror','-Wno-missing-field-initializers','-Wno-misleading-indentation','-rdynamic','-DRISC_INSTALLED_APP_CAPACITY=64','-DRISC_PROVIDER_CAPACITY=40','-DRISC_APP_POLICY_ROWS=32','-DRISC_APP_REQUIREMENT_ROWS=32','-DSTORE_ADMISSION_RADIO','-DSTORE_ADMISSION_HCI','-DSTORE_ADMISSION_I2S_RX','-DSTORE_ADMISSION_RADIO_IQ','-DSTORE_ADMISSION_IQ_LIFECYCLE','-DSTORE_ADMISSION_RUNTIME_FEATURES','-DSTORE_ADMISSION_KV_V2']
if args.app_data:flags+=['-DSTORE_ADMISSION_APP_DATA']
if args.cohort_store:flags+=['-DSTORE_ADMISSION_COHORT']
san=['-fsanitize=address,undefined','-fno-sanitize-recover=all','-fno-omit-frame-pointer','-no-pie'] if args.sanitize else []
sources=[N/p for p in ['src/bootstrap/Json.cpp','src/bootstrap/Board.cpp','src/bootstrap/Runtime.cpp','src/runtime/drivers/ProviderGraphV2.cpp','src/runtime/drivers/ProviderModuleV2.cpp','src/ports/esp32s3/CpuPort.cpp','src/runtime/streams/AppStreamSessions.cpp','src/runtime/streams/ProviderQueueHost.cpp']]
subprocess.run(['cc','-std=c11',*san,*['-I'+str(p) for p in incs],'-c',str(N/'lib/elf_loader/src/esp_elf_validate.c'),'-o',str(out/'validate.o')],check=True)
subprocess.run(['c++',*flags,*san,*['-I'+str(p) for p in incs],*map(str,sources),str(out/'admission.cpp'),str(out/'validate.o'),'-ldl','-o',str(out/'admit')],check=True)
subprocess.run([str(out/'admit'),str(args.store.resolve())]+([str(args.cohort_store.resolve())] if args.cohort_store else []),check=True)
