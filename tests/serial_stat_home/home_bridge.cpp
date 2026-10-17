#include <cassert>
#include "bootstrap/RuntimeFiles.h"
extern "C" {const risc_storage_volume_api_v1 *probe_start();uint64_t probe_begin();void probe_end(uint64_t);void probe_cleanup();}
static RiscBoot::RuntimeFiles files;
static uint64_t session;
extern "C" void home_probe_start(){assert(files.bindVolume(probe_start(),[](){return true;},[](){return true;}));session=probe_begin();}
extern "C" int home_probe_stat(){risc_storage_files_stat_v1 st{sizeof(st),0,0,0};int rc=files.stat("/",&st);assert(!files.retained()&&files.exitSafe());return rc;}
extern "C" void home_probe_ready(){assert(session);probe_end(session);session=0;}
extern "C" void home_probe_finish(){if(session)home_probe_ready();assert(files.exitSafe());probe_cleanup();}
