/* Actual ordinary/async SD provider and FatFs; RAM media, no physical device. */
#define main existing_storage_test_main
#if TEST_SLEEP_ASYNC
#include "test_storage_async.c"
#else
#include "test_storage.c"
#endif
#undef main

static bool fail_sleep_sync;
static unsigned dat3_writes;
static bool sleep_sync(void*c,uint64_t t){
 if(fail_sleep_sync){(void)c;(void)t;++calls_;return false;}
 return sync_(c,t);
}
static bool sleep_select_write(void*c,uint64_t t,bool high){
 ++dat3_writes;assert(high);return select_write(c,t,high);
}
#if TEST_SLEEP_ASYNC
static bool sleep_work_sync(void*c){return sleep_sync(c,99);}
static bool sleep_work_power(void*c,bool high){
 (void)c;++dat3_writes;assert(high);return true;
}
#endif
static void assert_retained(const risc_storage_volume_api_v1*v,
                            const risc_storage_volume_api_v1_sleep*s){
 const unsigned before=calls_;
 assert(s->resume_sleep(NULL)==RISC_STORAGE_SLEEP_RETAINED);
 assert(!s->prepare_sleep(NULL)&&!s->commit_sleep(NULL));
 assert(!v->ready(NULL)&&!v->refresh(NULL)&&!quiesce());
 assert(!v->file_open_write(NULL,"/no-retry.txt"));
#if TEST_SLEEP_ASYNC
 uint64_t session=99;
 assert(observe_state(NULL)==RISC_STORAGE_STATE_RETAINED);
 assert(async_begin_checked(NULL,&session)==RISC_STORAGE_ASYNC_RETAINED&&!session);
 uint64_t export_id=99;assert(export_begin_prepare(NULL,&export_id)==RISC_STORAGE_EXPORT_RETAINED&&!export_id);
#endif
 assert(calls_==before&&!dat3_writes);
}
int main(int argc,char**argv){
 assert(argc==2);const char* mode=argv[1];make_disk();
 gpio_.base.write=sleep_select_write;gpio_.sdmmc.sync=sleep_sync;
#if TEST_SLEEP_ASYNC
 work_io_.sync=sleep_work_sync;work_io_.power=sleep_work_power;
 risc_provider_dependency_v1 deps[5];memcpy(deps,deps_,sizeof(deps_));
 deps[4]=(risc_provider_dependency_v1){RISC_STORAGE_WORKER_CAPABILITY,1,&worker_};
#else
 const risc_provider_dependency_v1*deps=deps_;
#endif
 const risc_driver_v2*d=t5_driver_get(2);assert(d);
 const risc_storage_volume_api_v1*v=d->capability;
 const risc_storage_volume_api_v1_ext*x=risc_storage_volume_extension(v);
 const risc_storage_volume_api_v1_sleep*s=risc_storage_volume_sleep(v);
 const risc_storage_volume_api_v1_power*power=risc_storage_volume_power(v);
 const risc_storage_volume_api_v1_power_commit*terminal=risc_storage_volume_power_commit(v);
 assert(x&&s&&power&&terminal);
 missing_=!strcmp(mode,"absent-boot");
 assert(start(deps,TEST_SLEEP_ASYNC?5:4));
#if TEST_SLEEP_ASYNC
 assert(!opened_&&v->refresh(NULL));
#endif
 assert(v->ready(NULL)!=missing_);
 if(missing_){
  assert(s->prepare_sleep(NULL)&&s->commit_sleep(NULL));
  assert(!opened_&&selected_&&s->resume_sleep(NULL)==RISC_STORAGE_SLEEP_MEDIA_UNAVAILABLE);
  const unsigned before=calls_;
  assert(s->resume_sleep(NULL)==RISC_STORAGE_SLEEP_MEDIA_UNAVAILABLE&&calls_==before);
  missing_=false;assert(v->refresh(NULL)&&v->ready(NULL));
  clean();free(image_);puts("Storage sleep absent boot/recovery PASS");return 0;
 }
 assert(opened_&&selected_);
 const unsigned beforeOwner=calls_;
 owner_=false;assert(!s->prepare_sleep(NULL)&&!s->commit_sleep(NULL));
 assert(s->resume_sleep(NULL)==RISC_STORAGE_SLEEP_REFUSED&&calls_==beforeOwner);owner_=true;
 // All ordinary handles fence a zero-handle transaction, including readers.
 uint32_t file=v->file_open_write(NULL,"/sleep.txt");assert(file);
 assert(v->file_write(NULL,file,"preserved",9)==9);
 assert(!s->prepare_sleep(NULL)&&!s->commit_sleep(NULL));
 assert(v->file_close(NULL,file,true));
 uint64_t size=0;file=v->file_open_read(NULL,"/sleep.txt",&size);assert(file&&size==9);
 unsigned before=calls_;assert(!s->prepare_sleep(NULL)&&calls_==before);
 assert(s->resume_sleep(NULL)==RISC_STORAGE_SLEEP_READY);
 assert(v->file_close(NULL,file,true));const uint32_t stale_file=file;
 risc_storage_dir_t dir=v->dir_open(NULL,"/");assert(dir);
 before=calls_;assert(!s->prepare_sleep(NULL)&&calls_==before);
 assert(x->dir_close_checked(NULL,dir));const risc_storage_dir_t stale_dir=dir;
#if TEST_SLEEP_ASYNC
 uint64_t session=0;assert(async_begin_checked(NULL,&session)==RISC_STORAGE_ASYNC_OK&&session);
 before=calls_;assert(!s->prepare_sleep(NULL)&&!s->commit_sleep(NULL));
 assert(s->resume_sleep(NULL)==RISC_STORAGE_SLEEP_REFUSED&&calls_==before);end_ok(session);
 uint64_t export_id=0,sectors=0;uint32_t sector_size=0;
 assert(export_begin(NULL,&export_id,&sectors,&sector_size)==RISC_STORAGE_EXPORT_READY);
 before=calls_;assert(!s->prepare_sleep(NULL)&&!s->commit_sleep(NULL));
 assert(s->resume_sleep(NULL)==RISC_STORAGE_SLEEP_REFUSED&&calls_==before);
 assert(export_end(NULL,export_id)==RISC_STORAGE_EXPORT_READY);
#endif
 if(!strcmp(mode,"sync-failure")){
  fail_sleep_sync=true;assert(!s->prepare_sleep(NULL));fail_sleep_sync=false;
  assert_retained(v,s);free(image_);puts("Storage sleep sync failure retains without retry PASS");return 0;
 }
 if(!strcmp(mode,"unlock-failure")){
  fail_unlock_=true;assert(!s->prepare_sleep(NULL));fail_unlock_=false;
  assert_retained(v,s);free(image_);puts("Storage sleep unlock failure retains without retry PASS");return 0;
 }
 // A cancelled preparation must restore admission without a transport cycle.
 assert(s->prepare_sleep(NULL));before=calls_;
 assert(s->prepare_sleep(NULL)&&calls_==before);
 assert(!v->ready(NULL)&&!v->refresh(NULL)&&!v->dir_open(NULL,"/"));
 assert(!v->file_open_read(NULL,"/sleep.txt",&size));
 assert(!power->cancel_power_down(NULL)&&!terminal->commit_power_down(NULL));
 assert(s->resume_sleep(NULL)==RISC_STORAGE_SLEEP_READY&&calls_==before&&opened_);
 assert(s->resume_sleep(NULL)==RISC_STORAGE_SLEEP_READY&&calls_==before);
 if(!strcmp(mode,"legacy")){
  assert(power->prepare_power_down(NULL)&&!s->prepare_sleep(NULL));
  assert(s->resume_sleep(NULL)==RISC_STORAGE_SLEEP_REFUSED);
  assert(terminal->commit_power_down(NULL)&&!opened_);
  assert(!power->cancel_power_down(NULL));
  assert(s->resume_sleep(NULL)==RISC_STORAGE_SLEEP_REFUSED);
  clean();assert(!dat3_writes);free(image_);puts("Storage sleep legacy transaction remains terminal PASS");return 0;
 }
 assert(s->prepare_sleep(NULL));
 if(!strcmp(mode,"close-failure")){
  fail_release_=true;assert(!s->commit_sleep(NULL));fail_release_=false;
  assert_retained(v,s);free(image_);puts("Storage sleep close failure retains without retry PASS");return 0;
 }
 assert(s->commit_sleep(NULL));before=calls_;
 assert(!opened_&&selected_&&!card_token&&!mounted&&!card_ready);
 assert(s->commit_sleep(NULL)&&calls_==before);
 assert(!s->prepare_sleep(NULL)&&!v->ready(NULL)&&!v->refresh(NULL));
#if TEST_SLEEP_ASYNC
 session=99;assert(async_begin_checked(NULL,&session)==RISC_STORAGE_ASYNC_BUSY&&!session);
 const uint64_t old_epoch=native_mount_epoch;
#endif
 if(!strcmp(mode,"absent-resume")||!strcmp(mode,"resume-close-failure"))missing_=true;
 if(!strcmp(mode,"resume-close-failure"))fail_release_=true;
 if(!strcmp(mode,"resume-read-failure"))fail_read_=true;
 if(!strcmp(mode,"unformatted"))memset(image_,0,512);
 const int32_t resumed=s->resume_sleep(NULL);
 if(!strcmp(mode,"resume-close-failure")||!strcmp(mode,"resume-read-failure")){
  assert(resumed==RISC_STORAGE_SLEEP_RETAINED);fail_release_=fail_read_=missing_=false;
  assert_retained(v,s);free(image_);puts("Storage sleep resume I/O/cleanup failure retains PASS");return 0;
 }
 const bool unavailable=missing_||!strcmp(mode,"unformatted");
 assert(resumed==(unavailable?RISC_STORAGE_SLEEP_MEDIA_UNAVAILABLE:RISC_STORAGE_SLEEP_READY));
 assert(v->ready(NULL)!=unavailable);before=calls_;
 assert(s->resume_sleep(NULL)==resumed&&calls_==before);
 if(unavailable){
  if(missing_){missing_=false;assert(v->refresh(NULL)&&v->ready(NULL));}
  clean();assert(!dat3_writes);free(image_);puts("Storage sleep clean absent/unformatted resume PASS");return 0;
 }
#if TEST_SLEEP_ASYNC
 assert(native_mount_epoch!=old_epoch&&observe_state(NULL)==RISC_STORAGE_STATE_READY);
#endif
 char bytes[9];risc_storage_dirent_v1 entry;
 assert(!v->file_read(NULL,stale_file,bytes,sizeof(bytes)));
 assert(!v->dir_next(NULL,stale_dir,&entry));
 assert(!v->file_close(NULL,stale_file,true)&&!x->dir_close_checked(NULL,stale_dir));
 file=v->file_open_read(NULL,"/sleep.txt",&size);assert(file&&file!=stale_file&&size==9);
 assert(v->file_read(NULL,file,bytes,sizeof(bytes))==9&&!memcmp(bytes,"preserved",9));
 assert(v->file_close(NULL,file,true));
 for(unsigned i=0;i<3;++i){assert(s->prepare_sleep(NULL)&&s->commit_sleep(NULL));assert(!opened_&&selected_);assert(s->resume_sleep(NULL)==RISC_STORAGE_SLEEP_READY);}
 clean();assert(!dat3_writes);free(image_);
 printf("Storage sleep async=%u: handles/session/export refusal, cancel/commit/reopen, stale handles, repeated cycles, DAT3 unchanged PASS\n",TEST_SLEEP_ASYNC);
 return 0;
}
