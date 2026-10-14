#define RUNTIME_ATOMIC_WIFI_CONTROLLER_HELPERS_ONLY
#include "runtime_atomic_wifi_controller.c"
extern void wave_yield(void);
static void drain(void){for(unsigned n=0;profile_work||remember_pending||forget_pending;++n){assert(n<1000);wifi_profiles_step();wave_yield();}}
void wave_wifi(const risc_runtime_api_v1*rt,unsigned phase){
 controller_start(rt);
 if(phase==0){
  controller_draft("Wave saved A","wave-password-a");wifi_activate(6);drain();
  controller_draft("Wave saved B","wave-password-b");wifi_activate(6);drain();
 }
 uint32_t count=0;assert(!portable_wifi_profile_count(wifi_store,&count)&&count==2);
 if(phase<3){controller_record(0,"Wave saved A","wave-password-a");controller_record(1,"Wave saved B","wave-password-b");}
 else {controller_record(0,"Wave saved A","changed-password-a");portable_wifi_credentials empty;assert(portable_wifi_profile_load(wifi_store,1,&empty)==PORTABLE_WIFI_CREDENTIALS_EMPTY);}
 if(phase==2){
  controller_draft("Wave saved A","changed-password-a");wifi_activate(6);drain();controller_record(0,"Wave saved A","changed-password-a");
  controller_draft("Wave saved B","wave-password-b");wifi_activate(7);drain();assert(page==WP_FORGET);wifi_activate(1);drain();
  portable_wifi_credentials empty;assert(portable_wifi_profile_load(wifi_store,1,&empty)==PORTABLE_WIFI_CREDENTIALS_EMPTY);
 }
 assert(!legacy_fallbacks&&!writes&&!profile_work);finish();assert(!broker_live&&broker_acquires==broker_releases);
}
