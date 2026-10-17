#define main existing_storage_main
#include "../test_storage_async.c"
#undef main
const risc_storage_volume_api_v1 *probe_start(void){
 make_disk();risc_provider_dependency_v1 deps[5];memcpy(deps,deps_,sizeof(deps_));deps[4]=(risc_provider_dependency_v1){RISC_STORAGE_WORKER_CAPABILITY,1,&worker_};
 const risc_driver_v2*d=t5_driver_get(2);assert(start(deps,5));assert(((const risc_storage_volume_api_v1*)d->capability)->refresh(NULL));return d->capability;
}
uint64_t probe_begin(void){uint64_t s=0;assert(async_begin_checked(NULL,&s)==0&&s);return s;}
void probe_end(uint64_t s){end_ok(s);}
bool probe_prepare(void){return prepare_sleep(NULL);}
int probe_resume(void){return resume_sleep(NULL);}
void probe_owner(bool value){owner_=value;}
void probe_io_failed(void){io_failed=true;}
void probe_cleanup(void){owner_=true;io_failed=false;clean();free(image_);}
