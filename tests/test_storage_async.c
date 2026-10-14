/* Real driver + unchanged FatFs on a RAM SD-card transport. No physical media. */
#include "DriverSupport.h"
#include "RiscGpioSdmmcV1.h"
#include "RiscProviderSyncV1.h"
#include <assert.h>
#include <stdlib.h>
#include <stdio.h>
static bool working_;
static uint8_t *image_;static const uint32_t sectors_=131072;
static bool owner_=true,locked_,created_,selected_,opened_,missing_,bad_info_,fail_release_,fail_unlock_,fail_destroy_,fail_select_,fail_read_;
static unsigned calls_,reads_,writes_,cut_;
static bool sync_owner(void*c){(void)c;return owner_;}
static bool sync_create(void*c,uint64_t*t){(void)c;*t=0;if(!owner_||created_)return false;created_=true;*t=8;return true;}
static bool sync_lock(void*c,uint64_t t){(void)c;assert(t==8&&created_);if(!owner_||locked_)return false;locked_=true;return true;}
static bool sync_unlock(void*c,uint64_t t){(void)c;assert(t==8&&created_&&(locked_||working_));if(fail_unlock_)return false;locked_=false;return true;}
static bool sync_destroy(void*c,uint64_t t){(void)c;assert(t==8&&created_&&!locked_);if(fail_destroy_)return false;created_=false;return true;}
static bool select_claim(void*c,uint8_t pin,bool output,bool initial,bool pull,uint64_t*t){(void)c;assert(pin==17&&output&&initial&&!pull);*t=0;if(fail_select_)return false;assert(!selected_);selected_=true;*t=18;return true;}
static bool select_write(void*c,uint64_t t,bool v){(void)c;assert(t==18&&selected_&&v);return true;}
static bool select_release(void*c,uint64_t t){(void)c;assert(t==18&&selected_&&!opened_);selected_=false;return true;}
static uint64_t now_(void*c){(void)c;return 0;}
static void sleep_(void*c,uint32_t ms){(void)c;(void)ms;}
static bool open_(void*c,uint8_t clk,uint8_t cmd,uint8_t d0,uint32_t hz,uint64_t*t,risc_sdmmc_card_info_v1*i){
 (void)c;assert(clk==2&&cmd==1&&d0==3&&hz==20000000&&selected_&&(locked_||working_)&&!opened_);calls_++;opened_=true;*t=99;
 *i=(risc_sdmmc_card_info_v1){sizeof(*i),bad_info_?1024:512,sectors_,20000000,0};return !missing_;
}
static bool read_(void*c,uint64_t t,uint64_t lba,uint32_t n,void*b){(void)c;assert(t==99&&opened_&&(locked_||working_)&&n==1&&lba<sectors_);calls_++;reads_++;if(fail_read_)return false;memcpy(b,image_+lba*512,512);return true;}
static bool write_(void*c,uint64_t t,uint64_t lba,uint32_t n,const void*b){(void)c;assert(t==99&&opened_&&(locked_||working_)&&n==1&&lba<sectors_);calls_++;writes_++;if(writes_==cut_)return false;memcpy(image_+lba*512,b,512);return true;}
static bool sync_(void*c,uint64_t t){(void)c;assert(t==99&&opened_&&(locked_||working_));calls_++;return true;}
static bool release_(void*c,uint64_t t){(void)c;assert(t==99&&opened_&&(locked_||working_));calls_++;if(fail_release_)return false;opened_=false;return true;}
static risc_gpio_sdmmc_api_v1 gpio_={.base={.api_version=1,.struct_size=sizeof(gpio_),.claim=select_claim,.write=select_write,.release=select_release},.sdmmc_tag=RISC_GPIO_SDMMC_TAG_V1,.sdmmc_version=1,.sdmmc={1,sizeof(risc_sdmmc_host_api_v1),NULL,open_,read_,write_,sync_,release_}};
static risc_platform_clock_api_v1 clock_={1,sizeof(clock_),NULL,now_,sleep_};
static risc_provider_sync_api_v1 sync_api_={1,sizeof(sync_api_),NULL,sync_owner,sync_create,sync_lock,sync_unlock,sync_destroy};
static risc_hw_gpio_bank_v1 config_={.struct_size=sizeof(config_),.count=4,.active_high=1,.pull_up=1,.pins={2,1,3,17}};
static risc_hardware_device_v1 hardware_={.api_version=1,.struct_size=sizeof(hardware_),.instance_id=8,.compatible="sd,sd-memory-1bit",.revision="unspecified",.config_type="gpio.bank",.config_version=1,.config_size=sizeof(config_),.config=&config_};
static risc_provider_dependency_v1 deps_[]={{"hardware.device",1,&hardware_},{"platform.gpio",1,&gpio_},{"platform.clock",1,&clock_},{"platform.sync",1,&sync_api_}};
#include <RiscStorageWorkerV1.h>
static risc_storage_work_execute_v1 execute_;static void*execute_context_;
static uint8_t request_[RISC_STORAGE_WORKER_BYTES],result_[RISC_STORAGE_WORKER_BYTES];
static uint32_t request_size_,result_size_;static int32_t result_status_;static uint64_t job_,serial_;static bool completed_;
static int32_t work_claim(void*c,const risc_storage_work_scope_v1*s){(void)c;assert(owner_&&!selected_&&s->power==17&&s->clk==2&&s->cmd==1&&s->dat0==3&&s->initial_power_level&&s->max_hz==20000000);selected_=true;return 0;}
static int32_t work_release(void*c){(void)c;assert(owner_&&!job_&&!opened_&&selected_);selected_=false;return 0;}
static int32_t work_bind(void*c,risc_storage_work_execute_v1 f,void*p){(void)c;assert(owner_&&selected_&&!execute_);execute_=f;execute_context_=p;return 0;}
static int32_t work_unbind(void*c){(void)c;assert(owner_&&!job_);execute_=NULL;return 0;}
static int32_t work_submit(void*c,const void*q,uint32_t n,uint64_t*t){(void)c;assert(owner_&&n<=sizeof(request_));*t=0;if(job_)return RISC_STORAGE_WORK_BUSY;memcpy(request_,q,n);request_size_=n;*t=job_=++serial_;completed_=false;return 0;}
static int32_t work_collect(void*c,uint64_t t,void*out,uint32_t cap,uint32_t*n,int32_t*status){(void)c;assert(owner_);if(!job_||t!=job_)return RISC_STORAGE_WORK_INVALID;if(!completed_)return RISC_STORAGE_WORK_PENDING;assert(cap>=result_size_);memcpy(out,result_,result_size_);*n=result_size_;*status=result_status_;job_=0;completed_=false;return 0;}
static int32_t work_cancel(void*c,uint64_t t){(void)c;assert(owner_);if(!job_||t!=job_)return RISC_STORAGE_WORK_INVALID;if(completed_)return RISC_STORAGE_WORK_OK;job_=0;return RISC_STORAGE_WORK_CANCELLED;}
static void pump(void){assert(job_&&!completed_&&execute_);working_=true;owner_=false;result_status_=execute_(execute_context_,request_,request_size_,result_,sizeof(result_),&result_size_);owner_=true;working_=false;completed_=true;}
static bool work_on(void*c){(void)c;return working_;}
static bool work_power(void*c,bool level){(void)c;assert(level);return true;}
static bool work_open(void*c,risc_sdmmc_card_info_v1*i){uint64_t ignored;return open_(c,2,1,3,20000000,&ignored,i);}
static bool work_read(void*c,uint64_t l,uint32_t n,void*b){return read_(c,99,l,n,b);}
static bool work_write(void*c,uint64_t l,uint32_t n,const void*b){return write_(c,99,l,n,b);}
static bool work_sync(void*c){return sync_(c,99);}
static bool work_close(void*c){return opened_?release_(c,99):true;}
static risc_storage_work_io_v1 work_io_={NULL,work_on,now_,work_power,sleep_,work_open,work_read,work_write,work_sync,work_close};
static risc_storage_worker_v1 worker_={1,sizeof(worker_),NULL,work_bind,work_submit,work_collect,work_cancel,work_unbind,work_claim,work_release,&work_io_};
#define WAVE_SD_ASYNC 1
#include "../drivers/storage_sdmmc/driver.c"
static void put16(uint8_t*p,uint16_t v){p[0]=v;p[1]=v>>8;}
static void put32(uint8_t*p,uint32_t v){for(unsigned i=0;i<4;i++)p[i]=v>>(8*i);}
static void make_disk(void) {
 image_=calloc(sectors_,512);assert(image_);uint8_t*b=image_;b[0]=0xeb;b[1]=0x58;b[2]=0x90;memcpy(b+3,"MSDOS5.0",8);
 put16(b+11,512);b[13]=1;put16(b+14,32);b[16]=2;b[21]=0xf8;put32(b+32,sectors_);put32(b+36,1024);put32(b+44,2);put16(b+48,1);
 b[66]=0x29;memcpy(b+82,"FAT32   ",8);b[510]=0x55;b[511]=0xaa;
 for(unsigned f=0;f<2;f++){uint8_t*p=image_+(32+f*1024)*512;put32(p,0xffffff8);put32(p+4,0xffffffff);put32(p+8,0xfffffff);}
}
static void clean(void){assert(quiesce());assert(!opened_&&!selected_&&!created_&&!locked_);}

static void collect_ok(uint64_t session,uint64_t token,risc_storage_async_result_v1*r){
 assert(async_collect(NULL,session,token,r)==RISC_STORAGE_ASYNC_PENDING);pump();assert(async_collect(NULL,session,token,r)==RISC_STORAGE_ASYNC_OK);assert(r->status==0);
}
static void end_ok(uint64_t s){for(unsigned i=0;i<5;++i){int rc=async_end(NULL,s);if(!rc)return;assert(rc==RISC_STORAGE_ASYNC_PENDING||rc==RISC_STORAGE_ASYNC_BUSY);if(job_&&!completed_)pump();}assert(false);}
int main(int argc,char**argv){
 make_disk();risc_provider_dependency_v1 deps[5];memcpy(deps,deps_,sizeof(deps_));deps[4]=(risc_provider_dependency_v1){RISC_STORAGE_WORKER_CAPABILITY,1,&worker_};
 const risc_driver_v2*d=t5_driver_get(2);const risc_storage_volume_api_v1*v=d->capability;
 assert(risc_storage_volume_native_capacity(v)&&risc_storage_volume_session_admission(v));
 risc_storage_work_io_v1 invalid_io=work_io_;invalid_io.read=NULL;
 worker_.io=&invalid_io;assert(!start(deps,5)&&!created_&&!selected_&&!opened_);worker_.io=&work_io_;
 unsigned before=calls_;assert(start(deps,5)&&calls_==before&&!opened_); // no I/O on activation
 if(argc>1&&!strcmp(argv[1],"missing")){
  missing_=true;assert(v->refresh(NULL)&&!v->ready(NULL)&&!opened_&&!poisoned);missing_=false;
  assert(v->refresh(NULL)&&v->ready(NULL));clean();free(image_);puts("Absent card cleanup and recovery PASS");return 0;
 }
 assert(v->refresh(NULL)&&v->ready(NULL));
 if(argc>1&&!strcmp(argv[1],"retained")){
  fail_release_=true;assert(!quiesce()&&opened_&&selected_&&created_);
  fail_release_=false;clean();free(image_);puts("Failed close retains custody; successful retry releases resources PASS");return 0;
 }
 uint32_t ordinary=v->file_open_write(NULL,"/ordinary.txt");assert(ordinary);
 uint64_t session=99;before=calls_;assert(async_begin_checked(NULL,&session)==RISC_STORAGE_ASYNC_BUSY&&!session&&calls_==before);
 assert(v->file_write(NULL,ordinary,"keep",4)==4&&v->file_close(NULL,ordinary,true));
 owner_=false;session=99;assert(async_begin_checked(NULL,&session)==RISC_STORAGE_ASYNC_BUSY&&!session);owner_=true;
 assert(async_begin_checked(NULL,&session)==0&&session);before=calls_;
 assert(!quiesce()&&calls_==before);
 assert(!v->file_open_write(NULL,"/forbidden.txt")&&calls_==before);
 risc_storage_async_request_v1 refresh_request={.operation=RISC_STORAGE_ASYNC_REFRESH};uint64_t token=0;
 assert(async_submit(NULL,session,&refresh_request,&token)==0&&calls_==before);risc_storage_async_result_v1 result;
 collect_ok(session,token,&result);
 risc_storage_package_request_v1 q={.operation=RISC_STORAGE_PACKAGE_MKDIR};strcpy(q.path,"/RTECFG");assert(package_submit(NULL,session,&q,&token)==0);collect_ok(session,token,&result);
 strcpy(q.path,"/RTECFG/00000006");assert(package_submit(NULL,session,&q,&token)==0);collect_ok(session,token,&result);
 q.operation=RISC_STORAGE_PACKAGE_WRITE_SMALL;strcpy(q.path,"/RTECFG/00000006/profiles");memcpy(q.data,"net-a;net-b",11);q.size=11;
 assert(package_submit(NULL,session,&q,&token)==0);memset(q.data,0,sizeof(q.data));collect_ok(session,token,&result);end_ok(session);
 assert(!async_adapter.session&&observe_state(NULL)==RISC_STORAGE_STATE_READY);
 for(unsigned restart=0;restart<3;++restart){
  assert(async_begin_checked(NULL,&session)==0);risc_storage_async_request_v1 readq={.operation=RISC_STORAGE_ASYNC_READ_SMALL_FILE};strcpy(readq.path,"/RTECFG/00000006/profiles");assert(async_submit(NULL,session,&readq,&token)==0);collect_ok(session,token,&result);assert(result.size==11&&!memcmp(result.data,"net-a;net-b",11));end_ok(session);
 }
 clean();puts("Waveshare actual SDMMC/FatFs copied session: zero-I/O activation, warm admission, ordinary-handle fence, copied writes/reads and repeated clean session reentry PASS");free(image_);return 0;
}
