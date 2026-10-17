#include <cstdio>
#include <cassert>
#include <cstring>
#include "bootstrap/RuntimeFiles.h"
extern "C" {const risc_storage_volume_api_v1 *probe_start();uint64_t probe_begin();void probe_end(uint64_t);bool probe_prepare();int probe_resume();void probe_owner(bool);void probe_io_failed();void probe_cleanup();}
int main(int argc,char**argv){assert(argc==2);const auto*v=probe_start();RiscBoot::RuntimeFiles f;assert(f.bindVolume(v,[](){return true;},[](){return true;}));risc_storage_files_stat_v1 st{sizeof(st),0,0,0};assert(f.stat("/",&st)==RISC_FILES_OK);
 const char*m=argv[1];uint64_t s=0;
 if(!strcmp(m,"active-session"))s=probe_begin();else if(!strcmp(m,"sleep-prepared"))assert(probe_prepare());else if(!strcmp(m,"owner-refused"))probe_owner(false);else if(!strcmp(m,"io-unavailable"))probe_io_failed();else assert(false);
 const int result=f.stat("/",&st);printf("case=%s stat=%d retained=%d exit_safe=%d\n",m,result,f.retained(),f.exitSafe());
 if(!strcmp(m,"owner-refused"))assert(result==RISC_FILES_RETAINED&&f.retained()&&!f.exitSafe());else assert(result==RISC_FILES_UNAVAILABLE&&!f.retained()&&f.exitSafe());
 if(s){probe_end(s);assert(f.stat("/",&st)==RISC_FILES_OK);}if(!strcmp(m,"sleep-prepared")){assert(probe_resume()==RISC_STORAGE_SLEEP_READY);assert(f.stat("/",&st)==RISC_FILES_OK);}probe_cleanup();return 0;}
