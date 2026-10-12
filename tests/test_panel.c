#include "DriverSupport.h"
#include "RiscSpiQuadV1.h"
#include "RiscDisplaySpiV2.h"
#include <assert.h>
#include <stdio.h>
static uint64_t now_us;
static bool reset_claimed,bus_claimed,bus_active,reset_high,held_reset;
static unsigned io_calls,fail_io,commands,quad_calls,stops;
static uint8_t opcode,current_command,brightness_seen;
static uint16_t x_first,x_last,y_first,y_last;
static size_t received;
static uint8_t glass[410*502*2];
static bool pass(void){return ++io_calls!=fail_io;}
static uint64_t now(void *c){(void)c;return now_us/1000;}
static void delay(void *c,uint32_t ms){(void)c;now_us+=ms*1000u;}
static bool gpclaim(void*c,uint8_t pin,bool out,bool initial,bool pull,uint64_t*t){(void)c;assert(pin==8&&out&&!pull);*t=0;if(reset_claimed||!pass())return false;reset_claimed=true;reset_high=initial;*t=9;return true;}
static bool gpwrite(void*c,uint64_t t,bool v){(void)c;assert(reset_claimed&&t==9);if(!pass())return false;reset_high=v;return true;}
static bool gpread(void*c,uint64_t t,bool*v){(void)c;(void)t;*v=reset_high;return true;}
static bool gppwm(void*c,uint64_t t,uint32_t hz,uint16_t v,uint16_t max){(void)c;(void)t;(void)hz;(void)v;(void)max;assert(0);return false;}
static bool gpwave(void*c,uint64_t t,const uint32_t*n,size_t z){(void)c;(void)t;(void)n;(void)z;assert(0);return false;}
static bool gprelease(void*c,uint64_t t){(void)c;assert(t==9&&reset_claimed&&!held_reset);if(!pass())return false;reset_claimed=false;return true;}
static int32_t hold(void*c,uint64_t t,bool v){(void)c;assert(t==9&&reset_claimed);held_reset=v;return 0;}
static bool claimq(void*c,uint8_t clk,uint8_t d0,uint8_t d1,uint8_t d2,uint8_t d3,uint8_t cs,uint64_t*t){(void)c;assert(clk==11&&d0==4&&d1==5&&d2==6&&d3==7&&cs==12);*t=0;if(bus_claimed||!pass())return false;bus_claimed=true;*t=100;return true;}
static bool beginq(void*c,uint64_t t,uint32_t hz,uint8_t mode,uint32_t timeout){(void)c;assert(t==100&&bus_claimed&&!bus_active&&hz==40000000&&!mode&&timeout&&timeout<=20);bus_active=true;opcode=current_command=0;received=0;return pass();}
static bool exchange(void*c,uint64_t t,const uint8_t*tx,uint8_t*rx,size_t n){(void)c;assert(bus_active&&t==100&&tx&&!rx&&n&&n<=512);if(!pass())return false;now_us+=10+(n+19)/20;
 if(!opcode){assert(n==4&&tx[1]==0&&tx[3]==0&&(tx[0]==2||tx[0]==0x32));opcode=tx[0];current_command=tx[2];++commands;return true;}
 assert(opcode==2);
 if(current_command==0x2a){assert(n==4);x_first=((unsigned)tx[0]<<8)|tx[1];x_last=((unsigned)tx[2]<<8)|tx[3];assert(x_first==22&&x_last==431);}
 if(current_command==0x2b){assert(n==4);y_first=((unsigned)tx[0]<<8)|tx[1];y_last=((unsigned)tx[2]<<8)|tx[3];assert(y_first==y_last&&y_last<502);}
 if(current_command==0x51){assert(n==1);brightness_seen=tx[0];}
 return true;
}
static bool pixelsq(void*c,uint64_t t,const uint8_t*tx,size_t n){(void)c;assert(t==100&&bus_active&&opcode==0x32&&current_command==0x2c&&n&&n<=512&&!(n&1)&&received+n<=820);if(!pass())return false;now_us+=10+(n+19)/20;memcpy(glass+y_first*820+received,tx,n);received+=n;quad_calls++;return true;}
static bool endq(void*c,uint64_t t){(void)c;assert(bus_claimed&&t==100);if(!pass())return false;bus_active=false;now_us+=10;return true;}
static bool releaseq(void*c,uint64_t t){(void)c;assert(bus_claimed&&t==100&&!bus_active);if(!pass())return false;bus_claimed=false;stops++;return true;}
static garden_gpio_v1 pg={.api_version=1,.struct_size=sizeof(pg),.claim=gpclaim,.write=gpwrite,.read=gpread,.pwm=gppwm,.release=gprelease,.waveform=gpwave,.deep_sleep_hold=hold};
static risc_spi_quad_v1 qs={.base={.api_version=1,.struct_size=sizeof(qs),.begin=beginq,.exchange=exchange,.end=endq,.release=releaseq},.quad_tag=RISC_SPI_QUAD_TAG,.quad_version=1,.claim_quad=claimq,.exchange_quad=pixelsq};
static risc_platform_clock_api_v1 pc={1,sizeof(pc),NULL,now,delay};
static risc_hw_spi_display_v2 cfg;
static risc_hardware_device_v1 hw={.api_version=1,.struct_size=sizeof(hw),.instance_id=101,.compatible="chipone,co5300",.revision="unspecified",.config_type="display.spi",.config_version=2,.config_size=sizeof(cfg),.config=&cfg};
static risc_provider_dependency_v1 deps[]={{"hardware.device",1,&hw},{"platform.gpio",1,&pg},{"platform.clock",1,&pc},{"spi.bus",1,&qs}};
#include "../drivers/panel_co5300/driver.c"
static void setup(void){assert(!bus_claimed&&!reset_claimed&&!held_reset);cfg=(risc_hw_spi_display_v2){.base={.struct_size=sizeof(cfg),.bus={.struct_size=sizeof(risc_hw_bus_v1),.kind=RISC_HW_BUS_SPI,.instance_id=101,.controller=0,.sclk=11,.mosi=4,.miso=5,.sda=-1,.scl=-1,.frequency_hz=40000000},.cs=12,.reset=8,.dc=-1,.backlight=-1,.busy=-1,.width=410,.height=502,.offset_x=22},.data2=6,.data3=7};fail_io=io_calls=commands=quad_calls=0;}
static void frame(void){risc_display_surface_v1 f={0};assert(api.base.acquire(NULL,FORMAT,&f));assert(f.width==410&&f.height==502&&f.size_bytes==411640);for(unsigned y=0;y<502;y++)for(unsigned x=0;x<410;x++){uint16_t v=(uint16_t)(y*410+x);memcpy((uint8_t*)f.pixels+y*f.stride_bytes+x*2,&v,2);}risc_display_present_token_v1 token=0;assert(api.base.submit(NULL,f.frame,NULL,0,NULL,&token));assert(!api.prepare_sleep(NULL));risc_display_present_status_v1 status={0};for(unsigned i=0;i<600;i++){uint64_t t=now_us;display_poll(8);assert(now_us-t<10000);assert(api.base.present_status(NULL,token,&status));if(status.state==RISC_DISPLAY_PRESENT_COMPLETE)break;assert(status.state==RISC_DISPLAY_PRESENT_ACTIVE);}assert(status.state==RISC_DISPLAY_PRESENT_COMPLETE&&quad_calls>=1004);for(unsigned y=0;y<502;y++)for(unsigned x=0;x<410;x++){unsigned v=(y*410+x)&65535;assert(glass[y*820+x*2]==v>>8&&glass[y*820+x*2+1]==(v&255));}assert(brightness_seen==255);}
int main(void){setup();assert(start(deps,4));assert(now_us>=540000&&reset_high&&brightness_seen==0);risc_display_info_v1 info={0};assert(api.base.get_info(NULL,&info)&&info.width==410&&info.height==502);assert(api.base.set_brightness(NULL,100,100));assert(brightness_seen==0);frame();assert(api.prepare_sleep(NULL)&&brightness_seen==0);assert(!api.base.acquire(NULL,FORMAT,(risc_display_surface_v1[1]){{0}}));assert(api.resume(NULL)&&brightness_seen==0);frame();assert(api.prepare_deep_sleep(NULL)==0&&held_reset);assert(!quiesce());assert(api.resume(NULL)&&!held_reset);assert(quiesce()&&!bus_claimed&&!reset_claimed);
 setup();assert(start(deps,4));unsigned total=io_calls;assert(quiesce());for(unsigned i=1;i<=total;i++){setup();fail_io=i;assert(!start(deps,4));fail_io=0;assert(quiesce());assert(!bus_claimed&&!reset_claimed);}
 setup();cfg.data3=cfg.data2;assert(!start(deps,4));assert(quiesce());setup();qs.quad_tag=0;assert(!start(deps,4));assert(quiesce());qs.quad_tag=RISC_SPI_QUAD_TAG;
 setup();assert(start(deps,4));risc_display_surface_v1 f={0};assert(acquire(NULL,FORMAT,&f));uint64_t token=0;assert(submit(NULL,f.frame,NULL,0,NULL,&token));fail_io=io_calls+2;display_poll(8);assert(present_state==RISC_DISPLAY_PRESENT_FAILED);assert(!acquire(NULL,FORMAT,&f));fail_io=0;assert(quiesce());
 puts("CO5300 production driver: 410x502 pixels, x+22 window, Quad framing, frame lifetime, brightness, sleep/resume, startup/transfer cleanup PASS");return 0;}
