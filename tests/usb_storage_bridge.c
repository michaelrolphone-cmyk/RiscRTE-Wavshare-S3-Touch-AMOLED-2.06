#define main storage_fixture_main
#define t5_driver_get wave_driver_get
#include "test_storage_async.c"
#undef main
#undef t5_driver_get
const risc_storage_volume_api_v1_export_prepare *wave_test_start(void){
 make_disk();risc_provider_dependency_v1 deps[5];memcpy(deps,deps_,sizeof(deps_));
 deps[4]=(risc_provider_dependency_v1){RISC_STORAGE_WORKER_CAPABILITY,1,&worker_};
 const risc_storage_volume_api_v1*v=wave_driver_get(2)->capability;assert(start(deps,5)&&!opened_);
 assert(risc_storage_volume_sleep(v));return risc_storage_volume_export_prepare(v);
}
void wave_test_frozen(void){const risc_storage_volume_api_v1*v=wave_driver_get(2)->capability;assert(export_state==EXPORT_HOST&&!mounted&&!v->ready(NULL)&&!v->refresh(NULL));}
void wave_test_finish(void){
 const risc_storage_volume_api_v1*v=wave_driver_get(2)->capability;
 assert(export_state==EXPORT_LOCAL&&mounted&&v->ready(NULL));
 uint32_t f=v->file_open_write(NULL,"/usb-after.txt");assert(f&&v->file_write(NULL,f,"restored",8)==8&&v->file_close(NULL,f,true));
 clean();free(image_);
}
