/* Real driver + unchanged FatFs on a RAM SD-card transport. No physical media. */
#include "DriverSupport.h"
#include "RiscGpioSdmmcV1.h"
#include "RiscProviderSyncV1.h"
#include <assert.h>
#include <stdlib.h>
#include <stdio.h>
static uint8_t *image_;static const uint32_t sectors_=131072;
static bool owner_=true,locked_,created_,selected_,opened_,missing_,bad_info_,fail_release_,fail_unlock_,fail_destroy_,fail_select_;
static unsigned calls_,reads_,writes_,cut_;
static bool sync_owner(void*c){(void)c;return owner_;}
static bool sync_create(void*c,uint64_t*t){(void)c;*t=0;if(!owner_||created_)return false;created_=true;*t=8;return true;}
static bool sync_lock(void*c,uint64_t t){(void)c;assert(t==8&&created_);if(!owner_||locked_)return false;locked_=true;return true;}
static bool sync_unlock(void*c,uint64_t t){(void)c;assert(t==8&&created_&&locked_);if(fail_unlock_)return false;locked_=false;return true;}
static bool sync_destroy(void*c,uint64_t t){(void)c;assert(t==8&&created_&&!locked_);if(fail_destroy_)return false;created_=false;return true;}
static bool select_claim(void*c,uint8_t pin,bool output,bool initial,bool pull,uint64_t*t){(void)c;assert(pin==17&&output&&initial&&!pull);*t=0;if(fail_select_)return false;assert(!selected_);selected_=true;*t=18;return true;}
static bool select_write(void*c,uint64_t t,bool v){(void)c;assert(t==18&&selected_&&v);return true;}
static bool select_release(void*c,uint64_t t){(void)c;assert(t==18&&selected_&&!opened_);selected_=false;return true;}
static uint64_t now_(void*c){(void)c;return 0;}
static void sleep_(void*c,uint32_t ms){(void)c;(void)ms;}
static bool open_(void*c,uint8_t clk,uint8_t cmd,uint8_t d0,uint32_t hz,uint64_t*t,risc_sdmmc_card_info_v1*i){
 (void)c;assert(clk==2&&cmd==1&&d0==3&&hz==20000000&&selected_&&locked_&&!opened_);calls_++;opened_=true;*t=99;
 *i=(risc_sdmmc_card_info_v1){sizeof(*i),bad_info_?1024:512,sectors_,20000000,0};return !missing_;
}
static bool read_(void*c,uint64_t t,uint64_t lba,uint32_t n,void*b){(void)c;assert(t==99&&opened_&&locked_&&n==1&&lba<sectors_);calls_++;reads_++;memcpy(b,image_+lba*512,512);return true;}
static bool write_(void*c,uint64_t t,uint64_t lba,uint32_t n,const void*b){(void)c;assert(t==99&&opened_&&locked_&&n==1&&lba<sectors_);calls_++;writes_++;if(writes_==cut_)return false;memcpy(image_+lba*512,b,512);return true;}
static bool sync_(void*c,uint64_t t){(void)c;assert(t==99&&opened_&&locked_);calls_++;return true;}
static bool release_(void*c,uint64_t t){(void)c;assert(t==99&&opened_&&locked_);calls_++;if(fail_release_)return false;opened_=false;return true;}
static risc_gpio_sdmmc_api_v1 gpio_={.base={.api_version=1,.struct_size=sizeof(gpio_),.claim=select_claim,.write=select_write,.release=select_release},.sdmmc_tag=RISC_GPIO_SDMMC_TAG_V1,.sdmmc_version=1,.sdmmc={1,sizeof(risc_sdmmc_host_api_v1),NULL,open_,read_,write_,sync_,release_}};
static risc_platform_clock_api_v1 clock_={1,sizeof(clock_),NULL,now_,sleep_};
static risc_provider_sync_api_v1 sync_api_={1,sizeof(sync_api_),NULL,sync_owner,sync_create,sync_lock,sync_unlock,sync_destroy};
static risc_hw_gpio_bank_v1 config_={.struct_size=sizeof(config_),.count=4,.active_high=1,.pull_up=1,.pins={2,1,3,17}};
static risc_hardware_device_v1 hardware_={.api_version=1,.struct_size=sizeof(hardware_),.instance_id=8,.compatible="sd,sd-memory-1bit",.revision="unspecified",.config_type="gpio.bank",.config_version=1,.config_size=sizeof(config_),.config=&config_};
static risc_provider_dependency_v1 deps_[]={{"hardware.device",1,&hardware_},{"platform.gpio",1,&gpio_},{"platform.clock",1,&clock_},{"platform.sync",1,&sync_api_}};
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
int main(int argc,char**argv) {
 make_disk();const risc_storage_volume_api_v1*v=&api.volume.base;const risc_storage_volume_api_v1_ext*x=&api.volume;
 if(argc==2){
  assert(start(deps_,4));cut_=writes_+(unsigned)strtoul(argv[1],NULL,10);
  uint32_t h=v->file_open_write(NULL,"/uncertain.txt");
  if(h){char bytes[2048]={1};if(v->file_write(NULL,h,bytes,sizeof(bytes))==sizeof(bytes)) (void)v->file_close(NULL,h,true);}
  assert(io_failed);unsigned count=writes_;
  assert(!v->ready(NULL));assert(!v->file_open_write(NULL,"/retry.txt"));assert(writes_==count);
  puts("SD/FatFs uncertain sector write fenced without retry PASS");free(image_);return 0;
 }
 assert(t5_driver_get(2)&&!t5_driver_get(1));
 owner_=false;assert(!start(deps_,4)&&!calls_);owner_=true;
 fail_select_=true;assert(!start(deps_,4));clean();fail_select_=false;
 missing_=true;assert(start(deps_,4)&&!opened_&&!v->ready(NULL));clean();missing_=false;
 bad_info_=true;assert(start(deps_,4)&&!opened_&&!v->ready(NULL));clean();bad_info_=false;
 assert(start(deps_,4)&&v->ready(NULL));assert(!start(deps_,4));unsigned initial=calls_;
 owner_=false;assert(!v->ready(NULL)&&!v->refresh(NULL)&&!quiesce()&&calls_==initial);owner_=true;
 assert(x->mkdir(NULL,"/Books"));unsigned first=writes_;
 uint32_t file=v->file_open_write(NULL,"/Books/a long name.txt");assert(file);assert(!v->refresh(NULL)&&!quiesce());
 char payload[2048];for(unsigned i=0;i<sizeof(payload);i++)payload[i]=(char)i;
 assert(v->file_write(NULL,file,payload,sizeof(payload))==sizeof(payload));assert(v->file_close(NULL,file,true));
 printf("WRITE_CUTS=%u\n",writes_-first);
 uint64_t size=0;file=v->file_open_read(NULL,"/Books/a long name.txt",&size);assert(file&&size==sizeof(payload));
 char actual[2048];assert(v->file_read(NULL,file,actual,sizeof(actual))==sizeof(actual)&&!memcmp(actual,payload,sizeof(actual)));assert(x->file_seek(NULL,file,512));assert(v->file_read(NULL,file,actual,128)==128&&!memcmp(actual,payload+512,128));assert(v->file_close(NULL,file,true));
 assert(!v->file_read(NULL,file,actual,1));assert(x->rename(NULL,"/Books/a long name.txt","/Books/renamed.txt"));
 uint32_t dir=v->dir_open(NULL,"/Books");assert(dir);risc_storage_dirent_v1 ent;assert(v->dir_next(NULL,dir,&ent)&&!strcmp(ent.name,"renamed.txt"));assert(x->dir_close_checked(NULL,dir));
 assert(!v->file_open_write(NULL,"/../invalid"));assert(api.prepare_power_down(NULL));assert(!v->ready(NULL));assert(api.cancel_power_down(NULL));assert(v->ready(NULL));
 assert(v->refresh(NULL)&&v->ready(NULL));file=v->file_open_read(NULL,"/Books/renamed.txt",&size);assert(file&&size==2048);assert(v->file_close(NULL,file,true));
 fail_release_=true;assert(!quiesce()&&opened_&&selected_&&created_&&!locked_);fail_release_=false;clean();
 assert(start(deps_,4));fail_destroy_=true;assert(!quiesce()&&created_&&!opened_&&!selected_);fail_destroy_=false;clean();
 assert(start(deps_,4));fail_unlock_=true;assert(!v->ready(NULL)&&poisoned);initial=calls_;assert(!quiesce()&&!v->refresh(NULL)&&calls_==initial);
 free(image_);puts("SD/FatFs: real mount/read/write/seek/directory/remount, no-card boot, owner guard, power-down and retained cleanup PASS");return 0;
}
