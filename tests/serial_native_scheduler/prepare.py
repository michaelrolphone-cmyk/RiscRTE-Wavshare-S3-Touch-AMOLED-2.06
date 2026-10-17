from pathlib import Path
import sys,hashlib
r=Path(sys.argv[1]);o=Path(sys.argv[2]);o.mkdir(exist_ok=True,parents=True)
assert sys.argv[3] in ('baseline','fixed')
for name,digest in [('native_settings_maintenance_test.cpp','739b2b219ca17f36e3c8486fa67606865efb91e8231a0ab911077696f935ebc9'),('native_sd_port_test.cpp','c9678258fce6bb6ad137aaa1e12a063e48ee23bfdfe20cf8291f94e601e7ad76')]:
 assert hashlib.sha256((r/'test'/name).read_bytes()).hexdigest()==digest,'Upstream native fixture changed: '+name
s=(r/'test/native_sd_port_test.cpp').read_text().replace('pin==5','pin==17').replace('c==41&&m==42&&d==40','c==2&&m==1&&d==3')
(o/'native_sd_port_test.cpp').write_text(s)
s=(r/'test/native_settings_maintenance_test.cpp').read_text().replace('},9);','},12);').replace('},9,writers,2,bootstrapClient);','},12,writers,2,bootstrapClient);').replace('Pin anchor(runtime,cpu,9)','Pin anchor(runtime,cpu,12)').replace('P fresh(runtime,cpu,1,9)','P fresh(runtime,cpu,1,12)')
(o/'maintenance.cpp').write_text(s)
s=(o/'maintenance.cpp').read_text()
s=s.replace('#include <set>', '#include <set>\n#include "runtime/serial/Files.h"')
pos=s.index('static uint64_t asyncExport=0;')
s=s[:pos]+'''static RiscBoot::RuntimeFiles serialClient;
static RiscSerial::Files serialEndpoint;
static RiscSerial::Namespace serialNamespaces[]={{12,"SD card",&serialClient,true}};
static unsigned serialSequence=0,serialDispatch=0;
static bool serialSafe(){return !L::retained()&&(L::continuing()?port->nativeDiscoveryProviderSafe():port->providerStorageSafe());}
static std::string wire(const risc_runtime_api_v1* api,const char* cmd){
 std::string q="RTEF1 12345678 "+std::to_string(++serialSequence)+" "+cmd+"\\n";
 for(unsigned char b:q)serialEndpoint.input(b);
 const auto rc=api->service_checkpoint();
 std::string out;while(serialEndpoint.outputSize()){out.append(serialEndpoint.output(),serialEndpoint.outputSize());serialEndpoint.consumeOutput(serialEndpoint.outputSize());}
 printf("SERIAL_PROBE command=%s checkpoint=%d continuing=%d discovering=%d pinned=%d session=%llu volume=%d client_retained=%d app_exit=%d dispatch=%u wire=%s\\n",cmd,rc,L::continuing(),L::discovering(),port->nativeStorageAttached(),(unsigned long long)f->session(),risc_storage_volume_state(f->volume)->observe(f->volume->context),serialClient.retained(),port->nativeDiscoveryAppExitSafe(),serialDispatch,out.c_str());fflush(stdout);
 return out;
}
''' + s[pos:]
s=s.replace(' bool sawPinned=false;', ' wire(api,"HELLO");wire(api,"NS 0");wire(api,"PATH 0 2f6f7264696e6172792e747874");\n bool sawPinned=false,serialProbed=false;')
s=s.replace('sawPinned=true;assert(!port->providerStorageSafe()', 'if(!serialProbed&&f->session()){serialProbed=true;auto reply=wire(api,"STAT 12");assert(reply.find(" -3 ")!=std::string::npos);assert(!serialClient.retained());}\n   sawPinned=true;assert(!port->providerStorageSafe()')
s=s.replace(' boot.nativeDiscoveryCheckpoint=[]()', ' boot.serialFilesCheckpoint=[](){++serialDispatch;serialEndpoint.checkpoint();return serialEndpoint.custodySafe();};boot.serialFilesShutdown=[](){return serialEndpoint.shutdown();};\n boot.nativeDiscoveryCheckpoint=[]()')
s=s.replace('  const bool ran=runtime.run();', '  assert(serialClient.bindVolume(f->volume,owner,serialSafe));assert(serialEndpoint.bind(serialNamespaces,1,{owner,serialSafe,[](){return uint32_t(nowMs);}}));\n  const bool ran=runtime.run();')
(o/'maintenance.cpp').write_text(s)
s=(o/'maintenance.cpp').read_text()
s+='\nnamespace RiscCpu { namespace NativeSerialFiles { bool exitSafe(){return serialEndpoint.exitSafe();} bool custodySafe(){return serialEndpoint.custodySafe();} } }\n'
(o/'maintenance.cpp').write_text(s)
s=(o/'maintenance.cpp').read_text()
s=s.replace('#define NATIVE_FIXTURE_THREADED 1','#define NATIVE_FIXTURE_THREADED 1\n#define NATIVE_FIXTURE_EXTERNAL_SOURCE 1')
s+='''
namespace NativeFixture {
bool externalSourceDescriptor(int fd){
 char link[64],path[4096];std::snprintf(link,sizeof(link),"/proc/self/fd/%d",fd);
 const auto n=readlink(link,path,sizeof(path)-1);if(n<=0)return false;path[n]=0;
 const std::filesystem::path source(path);
 if(source.parent_path()!=std::filesystem::path(rootPath).parent_path())return false;
 const auto ext=source.extension();if(ext!=".json"&&ext!=".elf")return false;
 assert(owner());return true;
}
}
'''
(o/'maintenance.cpp').write_text(s)
s=(o/'maintenance.cpp').read_text().replace('assert(!anchor.acquire());','{const int rc=anchor.acquire();if(rc)fprintf(stderr,"ANCHOR rc=%d error=%s\\n",rc,runtime.error());assert(!rc);}')
s=s.replace('return serialEndpoint.exitSafe();','return !serialClient.bound() || serialEndpoint.exitSafe();').replace('return serialEndpoint.custodySafe();','return !serialClient.bound() || serialEndpoint.custodySafe();')
(o/'maintenance.cpp').write_text(s)
s=(o/'maintenance.cpp').read_text()
# Current Runtime activates native clients during run, before the first app. The
# legacy fixture's pre-run graph pin is invalid under that production sequence.
a=s.index('Pin anchor(runtime,cpu,12);');b=s.index('\nnamespace RiscCpu { namespace NativeSerialFiles',a)
s=s[:a]+'''
 assert(L::hydrate(runtime,cpu));assert(L::attachOwner(runtime,cpu));
 assert(runtime.bindNativeFiles("sdmmc-fatfs",12,serialClient,owner,serialSafe,true));
 assert(serialEndpoint.bind(serialNamespaces,1,{owner,serialSafe,[](){return uint32_t(nowMs);}}));
 const bool ran=runtime.run();
 fprintf(stderr,"FINAL ran=%d retained=%d error=%s lifecycle_retained=%d exit_safe=%d pinned=%d serial_retained=%d\\n",ran,runtime.retained(),runtime.error(),L::retained(),L::exitSafe(),cpu.nativeStorageAttached(),serialClient.retained());
 fflush(stdout);fflush(stderr);std::_Exit(ran?0:2);
}
''' +s[b:]
s=s.replace('boot.nativeSettingsShutdown=[](){const bool ok=L::shutdown();if(ok&&(asyncCase()||releaseAnchorAtFinal)){assert(!anchorPin->release()&&!f);releaseAnchorAtFinal=false;}return ok;};','boot.nativeSettingsShutdown=[](){return L::shutdown();};')
pos=s.index('static void unavailableApp()')
s=s[:pos]+'''static void serialNativeApp(){
 const auto*api=risc_runtime_get_api(1);assert(api&&f);
 printf("APP_START continuing=%d discovering=%d pinned=%d session=%llu\\n",L::continuing(),L::discovering(),port->nativeStorageAttached(),(unsigned long long)f->session());
 wire(api,"HELLO");wire(api,"NS 0");wire(api,"PATH 0 2f6f7264696e6172792e747874");
 risc_runtime_capability_v1 atomic{sizeof(atomic)};assert(api->acquire(RISC_KEY_VALUE_ATOMIC_CAPABILITY,1,1,&atomic));
 bool activeProbed=false,closedProbed=false;
 for(unsigned i=0;i<20000;++i){
  if(L::continuing()&&port->nativeStorageAttached()){
   const auto session=f->session();
   if(session&&!activeProbed){activeProbed=true;wire(api,"STAT 12");}
   if(!session&&!closedProbed){closedProbed=true;wire(api,"STAT 12");}
   if(scenario=="unavailable-return"&&activeProbed){printf("APP_RETURN_ACTIVE\\n");return;}
  }
  api->yield_ms(1);
  if(!risc_runtime_get_api(1)){printf("APP_AUTHORITY_LOST\\n");return;}
  if(activeProbed&&!L::continuing())break;
 }
 printf("PROBE_END active=%d closed=%d continuing=%d exit=%d pinned=%d\\n",activeProbed,closedProbed,L::continuing(),L::exitSafe(),port->nativeStorageAttached());
 if(serialClient.retained())return;
 wire(api,"STAT 12");
 assert(api->release(&atomic));
}
''' +s[pos:]
s=s.replace('extern "C" void test_maintenance_app(){','extern "C" void test_maintenance_app(){serialNativeApp();return;')
(o/'maintenance.cpp').write_text(s)
s=(o/'maintenance.cpp').read_text()
if sys.argv[3]=='fixed':
 s=s.replace('boot.serialFilesCheckpoint=[]()', 'boot.serialFilesReady=L::exitSafe;boot.serialFilesCheckpoint=[]()')
s=s.replace(' std::string q="RTEF1', ' if(serialEndpoint.pending()){printf("DEFERRED previous request still pending\\n");return {}; }\n std::string q="RTEF1')
s=s.replace('api->yield_ms(1);\n  if(!risc_runtime_get_api(1))','api->yield_ms(1);\n  if(serialEndpoint.pending()&&L::exitSafe()){const auto rc=api->service_checkpoint();std::string out;while(serialEndpoint.outputSize()){out.append(serialEndpoint.output(),serialEndpoint.outputSize());serialEndpoint.consumeOutput(serialEndpoint.outputSize());}printf("DEFERRED_RESPONSE rc=%d wire=%s\\n",rc,out.c_str());}\n  if(!risc_runtime_get_api(1))')
(o/'maintenance.cpp').write_text(s)

s=(o/'maintenance.cpp').read_text().replace('printf("APP_START', 'file("/ordinary.txt","keep",4);\n printf("APP_START')
(o/'maintenance.cpp').write_text(s)

s=(o/'maintenance.cpp').read_text()
s=s.replace(' const auto rc=api->service_checkpoint();', ' printf("SERIAL_BEFORE command=%s continuing=%d discovering=%d pinned=%d session=%llu volume=%d dispatch=%u\\n",cmd,L::continuing(),L::discovering(),port->nativeStorageAttached(),(unsigned long long)f->session(),risc_storage_volume_state(f->volume)->observe(f->volume->context),serialDispatch);\n const auto rc=api->service_checkpoint();')
(o/'maintenance.cpp').write_text(s)
