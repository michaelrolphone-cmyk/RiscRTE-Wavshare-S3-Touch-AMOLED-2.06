/* Generic storage.volume raw block lease. No filesystem or copied worker
 * session may coexist with a host export. Callbacks remain on the owner task. */
static int32_t export_retain(const char*s){export_state=EXPORT_RETAINED;fail(s);return RISC_STORAGE_EXPORT_RETAINED;}
static int32_t export_leave(int32_t r){return leave()?r:export_retain("SD export unlock retained");}
static int32_t export_denied(void){return poisoned||export_state==EXPORT_RETAINED||sleep_state==SLEEP_RETAINED?RISC_STORAGE_EXPORT_RETAINED:RISC_STORAGE_EXPORT_REFUSED;}
static int32_t export_begin_prepare(void*c,uint64_t*t){
 (void)c;if(!t)return RISC_STORAGE_EXPORT_REFUSED;*t=0;
 if(!enter_lifecycle())return export_denied();
 if(export_state==EXPORT_RETAINED||sleep_state==SLEEP_RETAINED)return export_leave(RISC_STORAGE_EXPORT_RETAINED);
 if(export_state!=EXPORT_LOCAL||!started||power_down_prepared||has_handles()||async_adapter.session||async_adapter.operation||async_adapter.retained||export_generation==UINT64_MAX)return export_leave(RISC_STORAGE_EXPORT_REFUSED);
 if(io_failed||!transport_idle())return export_leave(export_retain("SD media custody uncertain"));
 export_state=EXPORT_PREPARING;*t=export_token=++export_generation;
 return export_leave(RISC_STORAGE_EXPORT_PREPARING);
}
static int32_t export_prepare_step(void*c,uint64_t t,uint64_t*n,uint32_t*size){
 (void)c;if(!n||!size)return RISC_STORAGE_EXPORT_REFUSED;*n=0;*size=0;
 if(!enter_lifecycle())return export_denied();
 if(export_state==EXPORT_RETAINED||sleep_state==SLEEP_RETAINED)return export_leave(RISC_STORAGE_EXPORT_RETAINED);
 if(export_state!=EXPORT_PREPARING||!t||t!=export_token)return export_leave(RISC_STORAGE_EXPORT_REFUSED);
 if(!card_ready){(void)init_card();if(io_failed||poisoned)return export_leave(export_retain("SD preparation uncertain"));}
 if(!card_ready||!sector_count)return export_leave(RISC_STORAGE_EXPORT_REFUSED);
 if(!sync_card()||f_mount(NULL,"",0)!=FR_OK)return export_leave(export_retain("SD export sync/unmount retained"));
 mounted=false;export_state=EXPORT_HOST;*n=sector_count;*size=512;
 return export_leave(RISC_STORAGE_EXPORT_READY);
}
static int32_t export_begin(void*c,uint64_t*t,uint64_t*n,uint32_t*size){
 if(!n||!size){if(t)*t=0;return RISC_STORAGE_EXPORT_REFUSED;}*n=0;*size=0;
 int32_t r=export_begin_prepare(c,t);return r==RISC_STORAGE_EXPORT_PREPARING?export_prepare_step(c,*t,n,size):r;
}
static int32_t export_check(uint64_t t){return export_state==EXPORT_RETAINED||sleep_state==SLEEP_RETAINED?RISC_STORAGE_EXPORT_RETAINED:export_state==EXPORT_HOST&&t&&t==export_token?RISC_STORAGE_EXPORT_READY:RISC_STORAGE_EXPORT_REFUSED;}
static bool export_range(uint64_t l,uint32_t n,const void*b){return b&&n&&n<=RISC_STORAGE_EXPORT_BLOCKS_MAX&&n<=RISC_SDMMC_MAX_SECTORS&&l<sector_count&&n<=sector_count-l;}
static bool export_budget(uint32_t n){for(uint32_t i=0;i<n;i++)if(!disk_budget())return false;return true;}
static int32_t export_read(void*c,uint64_t t,uint64_t l,uint32_t n,void*b){
 (void)c;if(!enter_lifecycle())return export_denied();int32_t r=export_check(t);
 if(r!=RISC_STORAGE_EXPORT_READY)return export_leave(r);
 if(!export_range(l,n,b))return export_leave(RISC_STORAGE_EXPORT_REFUSED);
 if(!export_budget(n)||!storage_worker->io->read(storage_worker->io->context,l,n,b)){io_failed=true;return export_leave(export_retain("SD export read uncertain"));}
 return export_leave(RISC_STORAGE_EXPORT_READY);
}
static int32_t export_write(void*c,uint64_t t,uint64_t l,uint32_t n,const void*b){
 (void)c;if(!enter_lifecycle())return export_denied();int32_t r=export_check(t);
 if(r!=RISC_STORAGE_EXPORT_READY)return export_leave(r);
 if(!export_range(l,n,b))return export_leave(RISC_STORAGE_EXPORT_REFUSED);
 if(!export_budget(n)||!storage_worker->io->write(storage_worker->io->context,l,n,b)){io_failed=true;return export_leave(export_retain("SD export write uncertain; no retry"));}
 return export_leave(RISC_STORAGE_EXPORT_READY);
}
static int32_t export_sync(void*c,uint64_t t){
 (void)c;if(!enter_lifecycle())return export_denied();int32_t r=export_check(t);
 if(r==RISC_STORAGE_EXPORT_READY&&!sync_card())r=export_retain("SD export sync retained");
 return export_leave(r);
}
static int32_t export_end(void*c,uint64_t t){
 (void)c;if(!enter_lifecycle())return export_denied();
 if(export_state==EXPORT_RETAINED||sleep_state==SLEEP_RETAINED)return export_leave(RISC_STORAGE_EXPORT_RETAINED);
 if(!t||t!=export_token||(export_state!=EXPORT_HOST&&export_state!=EXPORT_PREPARING))return export_leave(RISC_STORAGE_EXPORT_REFUSED);
 if(export_state==EXPORT_HOST){
  if(!sync_card())return export_leave(export_retain("SD return sync retained"));
  mounted=false;(void)init_card();
  if(io_failed||poisoned)return export_leave(export_retain("SD remount retained"));
 }
 export_token=0;export_state=EXPORT_LOCAL;
 return export_leave(mounted&&card_ready?RISC_STORAGE_EXPORT_READY:RISC_STORAGE_EXPORT_MEDIA_UNAVAILABLE);
}
