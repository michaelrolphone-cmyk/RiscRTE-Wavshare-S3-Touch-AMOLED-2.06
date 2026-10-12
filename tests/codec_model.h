#pragma once
#include "DriverSupport.h"
#include "RiscAudioPcmV1.h"
#include "RiscI2sStandardV1.h"
#include "RiscI2sStandardConfigV1.h"
#include <assert.h>
#include <stdio.h>
static uint8_t registers_[2][256];
static bool owned_[2],amp_owned_,amp_level_,raw_owned_,fail_raw_open_,retain_raw_open_,fail_raw_close_;
static unsigned calls_,fail_at_,raw_opens_,raw_closes_;
static bool fail_write_,fail_read_,short_write_,short_read_;
static uint8_t directions_;
static uint32_t rate_;
static int16_t wire_[512];
static bool step_(void){return ++calls_!=fail_at_;}
static bool claim_(void *c,uint8_t address,uint64_t *token){(void)c;unsigned i=address==0x18?0:1;assert(address==0x18||address==0x40);*token=0;if(owned_[i]||!step_())return false;owned_[i]=true;*token=100+i;return true;}
static bool transfer_(void*c,uint64_t token,const uint8_t*tx,size_t n,uint8_t*rx,size_t rn,uint32_t ms){(void)c;assert(token>=100&&token<=101&&owned_[token-100]&&tx&&n&&ms==20);if(!step_())return false;if(rn){assert(n==1&&rn==1);*rx=registers_[token-100][*tx];}else{assert(n==2);registers_[token-100][*tx]=tx[1];}return true;}
static bool release_(void*c,uint64_t token){(void)c;assert(token>=100&&token<=101&&owned_[token-100]);if(!step_())return false;owned_[token-100]=false;return true;}
static bool gpclaim_(void*c,uint8_t pin,bool output,bool initial,bool pull,uint64_t*token){(void)c;assert(pin==46&&output&&!pull);*token=0;if(amp_owned_||!step_())return false;amp_owned_=true;amp_level_=initial;*token=77;return true;}
static bool gpwrite_(void*c,uint64_t token,bool value){(void)c;assert(token==77&&amp_owned_);amp_level_=value;return step_();}
static bool gprelease_(void*c,uint64_t token){(void)c;assert(token==77&&amp_owned_&&!amp_level_);if(!step_())return false;amp_owned_=false;return true;}
static bool raw_open_(void*c,uint8_t direction,uint32_t rate,uint64_t*token){(void)c;assert(!raw_owned_);*token=0;directions_=direction;rate_=rate;raw_opens_++;if(fail_raw_open_&&!retain_raw_open_)return false;raw_owned_=true;*token=1234;return !fail_raw_open_;}
static bool raw_write_(void*c,uint64_t token,const int16_t*pcm,size_t frames,size_t*done,uint32_t ms){(void)c;assert(token==1234&&raw_owned_&&directions_==3&&frames&&frames<=256&&ms<=40&&ms);*done=short_write_?frames-1:frames;memcpy(wire_,pcm,*done*4);return !fail_write_;}
static bool raw_read_(void*c,uint64_t token,int16_t*pcm,size_t frames,size_t*done,uint32_t ms){(void)c;assert(token==1234&&raw_owned_&&directions_==3&&frames&&frames<=256&&ms<=40&&ms);*done=short_read_?frames/2:frames;for(size_t i=0;i<*done;i++){pcm[2*i]=1000;pcm[2*i+1]=-2000;}return !fail_read_;}
static bool raw_close_(void*c,uint64_t token){(void)c;assert(raw_owned_&&token==1234);raw_closes_++;if(fail_raw_close_)return false;raw_owned_=false;return true;}
static risc_i2c_bus_api_v1 bus_={1,sizeof(bus_),NULL,claim_,transfer_,release_};
static garden_gpio_v1 gpio_={.api_version=1,.struct_size=sizeof(gpio_),.claim=gpclaim_,.write=gpwrite_,.release=gprelease_};
static risc_i2s_standard_api_v1 i2s_={1,sizeof(i2s_),NULL,raw_open_,raw_write_,raw_read_,raw_close_};
static risc_hw_i2s_standard_v1 configuration_={.struct_size=sizeof(configuration_),.bus={.struct_size=sizeof(risc_hw_bus_v1),.instance_id=100,.kind=2,.controller=0,.sda=15,.scl=14,.sclk=-1,.mosi=-1,.miso=-1,.frequency_hz=400000},.controller=0,.mclk=16,.bclk=41,.ws=45,.data_out=40,.data_in=42,.enable=46,.enable_active_high=1,.output_address=0x18,.input_address=0x40};
static risc_hardware_device_v1 hw_={1,sizeof(hw_),88,"everest,es8311-es7210","unspecified","audio.i2s-standard",1,sizeof(configuration_),&configuration_};
static risc_provider_dependency_v1 deps_[]={{"hardware.device",1,&hw_},{"i2c.bus",1,&bus_},{"platform.gpio",1,&gpio_},{"platform.i2s.standard",1,&i2s_}};
