#include "DriverSupport.h"
#include <assert.h>
#include <stdio.h>
static bool owned,level,fail_write,fail_release;
static uint64_t now;
static unsigned pin_no=18;
static bool claim_(void*c,uint8_t pin,bool output,bool initial,bool pull,uint64_t*t){(void)c;assert(pin==pin_no&&output&&!pull);if(owned)return false;owned=true;level=initial;*t=55;return true;}
static bool write_(void*c,uint64_t t,bool v){(void)c;assert(t==55&&owned);level=v;if(fail_write)return false;return true;}
static bool release_(void*c,uint64_t t){(void)c;assert(t==55&&owned);if(fail_release)return false;owned=false;return true;}
static uint64_t time_(void*c){(void)c;return now;}
static void sleep_(void*c,uint32_t ms){(void)c;now+=ms;}
static garden_gpio_v1 gp={.api_version=1,.struct_size=sizeof(gp),.claim=claim_,.write=write_,.release=release_};
static risc_platform_clock_api_v1 timer_={1,sizeof(timer_),NULL,time_,sleep_};
static risc_hw_gpio_bank_v1 cfg={.struct_size=sizeof(cfg),.count=1,.pins={18},.active_high=1};
static risc_hardware_device_v1 hardware={1,sizeof(hardware),7,"generic,erm-gpio","unspecified","gpio.bank",1,sizeof(cfg),&cfg};
static risc_provider_dependency_v1 deps[]={{"hardware.device",1,&hardware},{"platform.gpio",1,&gp},{"platform.clock",1,&timer_}};
#include "../drivers/haptic_gpio/driver.c"
int main(void) {
    for(unsigned polarity=0;polarity<=1;polarity++) {
        cfg.active_high=polarity;assert(start(deps,3)&&owned&&level!=polarity);
        assert(effect(NULL,1)&&level==polarity);now+=34;poll(1);assert(active);now++;poll(1);assert(!active&&level!=polarity);
        assert(effect(NULL,14));assert(off(NULL)&&level!=polarity);assert(!effect(NULL,124));
        assert(effect(NULL,47));fail_write=true;assert(!quiesce()&&owned);fail_write=false;
        fail_release=true;assert(!quiesce()&&owned&&level!=polarity);fail_release=false;assert(quiesce()&&!owned);
    }
    /* Different board pin, same provider code and public API. */
    pin_no=23;cfg.pins[0]=23;assert(start(deps,3)&&effect(NULL,1));assert(quiesce());
    assert(start(deps,3));fail_write=true;assert(!effect(NULL,1)&&failed);fail_write=false;now+=200;poll(1);assert(!active&&level!=cfg.active_high);assert(!effect(NULL,1));assert(quiesce());
    puts("ERM haptic: timed pulses, both polarities, alternate pins, explicit stop and cleanup failures PASS");
}
