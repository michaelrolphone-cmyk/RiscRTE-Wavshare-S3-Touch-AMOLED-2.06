/* Actual Wave SD/FatFs provider, RAM card and copied worker peripheral model. */
#define main original_storage_test_main
#include "test_storage_async.c"
#undef main
static bool partial_write(void*c,uint64_t l,uint32_t n,const void*b){(void)c;assert(n>1);memcpy(image_+l*512,b,512);writes_++;return false;}
int main(int argc,char**argv){
 const char*mode=argc>1?argv[1]:"normal";
 make_disk();risc_provider_dependency_v1 deps[5];memcpy(deps,deps_,sizeof(deps_));deps[4]=(risc_provider_dependency_v1){RISC_STORAGE_WORKER_CAPABILITY,1,&worker_};
 const risc_storage_volume_api_v1*v=t5_driver_get(2)->capability;
 assert(!risc_storage_volume_sleep(v)); // no invented sleep support
 const risc_storage_volume_api_v1_export_prepare*x=risc_storage_volume_export_prepare(v);assert(x);
 assert(start(deps,5)&&!opened_);
 uint64_t t=0,n=0;uint32_t size=0;unsigned before=calls_;
 assert(x->begin_prepare(NULL,&t)==RISC_STORAGE_EXPORT_PREPARING&&t&&calls_==before);
 assert(!v->refresh(NULL)&&!v->file_open_write(NULL,"/bad")&&!quiesce()&&calls_==before);
 uint64_t a=9;assert(async_begin_checked(NULL,&a)==RISC_STORAGE_ASYNC_BUSY&&!a);
 if(!strcmp(mode,"cancel")){assert(x->base.export_end(NULL,t)==RISC_STORAGE_EXPORT_MEDIA_UNAVAILABLE);clean();free(image_);puts("Unopened preparation cancellation releases without I/O PASS");return 0;}
 if(!strcmp(mode,"missing")){missing_=true;assert(x->prepare_step(NULL,t,&n,&size)==RISC_STORAGE_EXPORT_REFUSED);assert(x->base.export_end(NULL,t)==RISC_STORAGE_EXPORT_MEDIA_UNAVAILABLE);missing_=false;assert(v->refresh(NULL)&&v->ready(NULL));clean();free(image_);puts("Missing card cancels and refresh recovers PASS");return 0;}
 assert(x->prepare_step(NULL,t,&n,&size)==0&&n==sectors_&&size==512&&!mounted);
 uint8_t data[4097],old[4096];for(unsigned i=0;i<sizeof(data);i++)data[i]=(uint8_t)(i*13);
 assert(x->base.export_read(NULL,t,9000,8,old)==0);
 if(!strcmp(mode,"read-fail")){fail_read_=true;assert(x->base.export_read(NULL,t,9000,8,data+1)==RISC_STORAGE_EXPORT_RETAINED);}
 else if(!strcmp(mode,"partial-write")){work_io_.write=partial_write;assert(x->base.export_write(NULL,t,9000,8,data+1)==RISC_STORAGE_EXPORT_RETAINED);}
 else if(!strcmp(mode,"unlock-fail")){fail_unlock_=true;assert(x->base.export_read(NULL,t+1,9000,8,data+1)==RISC_STORAGE_EXPORT_RETAINED);}
 else {
  before=calls_;assert(x->base.export_read(NULL,t+1,9000,8,data)==-1);assert(x->base.export_read(NULL,t,sectors_-1,2,data)==-1);assert(x->base.export_read(NULL,t,9000,9,data)==-1);assert(calls_==before);
  unsigned r=reads_,w=writes_;
  for(unsigned i=0;i<512;i++){assert(x->base.export_write(NULL,t,9000,8,data+1)==0);uint8_t copy[4096];assert(x->base.export_read(NULL,t,9000,8,copy)==0);assert(!memcmp(copy,data+1,4096));}
  assert(reads_-r==512&&writes_-w==512);printf("4 MiB payload: 512 reads + 512 writes (eight sectors/call); exact unaligned bytes PASS\n");
  assert(x->base.export_write(NULL,t,9000,8,old)==0);
  assert(x->base.export_read(NULL,t,sectors_-1,1,data)==0);
  assert(x->base.export_sync(NULL,t)==0&&x->base.export_end(NULL,t)==0&&v->ready(NULL));
  uint32_t f=v->file_open_write(NULL,"/after.txt");assert(f&&v->file_write(NULL,f,"good",4)==4&&v->file_close(NULL,f,true));
  before=calls_;assert(x->begin_prepare(NULL,&t)==2);uint64_t stale=t;assert(x->base.export_end(NULL,t)==0);assert(x->begin_prepare(NULL,&t)==2&&t!=stale);assert(x->base.export_end(NULL,stale)==-1);assert(x->base.export_end(NULL,t)==0);assert(calls_==before);
  clean();free(image_);puts("Filesystem/async exclusion, generation, local remount and reuse PASS");return 0;
 }
 before=calls_;assert(export_state==EXPORT_RETAINED&&!quiesce());assert(x->base.export_read(NULL,t,0,1,data)==RISC_STORAGE_EXPORT_RETAINED);assert(x->base.export_write(NULL,t,0,1,data)==RISC_STORAGE_EXPORT_RETAINED);assert(x->base.export_end(NULL,t)==RISC_STORAGE_EXPORT_RETAINED);assert(!v->refresh(NULL)&&calls_==before);free(image_);puts("Uncertain I/O/unlock retains all resources without replay PASS");return 0;
}
