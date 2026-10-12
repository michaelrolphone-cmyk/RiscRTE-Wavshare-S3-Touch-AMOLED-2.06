/* Generic ERM motor pulse provider. The board descriptor supplies polarity and
 * pin; haptic.effect is the same application contract as an I2C haptic driver.
 * Bounded pulse approximations, not a claim of DRV2605 waveform reproduction. */
#include "DriverSupport.h"
#include "twatch_caps.h"
static const garden_gpio_v1 *gpio;
static const risc_platform_clock_api_v1 *clock_api;
static const risc_hw_gpio_bank_v1 *config;
static uint64_t claim,deadline;
static bool active,started,failed;
static bool off(void *context) {
    (void)context;
    if(!claim)return true;
    if(!gpio->write(gpio->context,claim,!config->active_high))return false;
    active=false;deadline=0;return true;
}
static bool effect(void *context,uint8_t id) {
    (void)context;if(!started || failed)return false;
    if(!id)return off(NULL);
    if(id>123)return false;
    /* Keep the established effect vocabulary. ERM gives a duration envelope. */
    unsigned ms=id==1?35:id==14?70:id==47?120:60;
    /* A failed write can have reached the pin. Keep an off deadline and
     * retry blanking; do not permit further pulses until teardown succeeds. */
    active=true;deadline=clock_api->monotonic_ms(clock_api->context)+ms;
    if(!gpio->write(gpio->context,claim,config->active_high)){failed=true;(void)off(NULL);return false;}
    return true;
}
static void poll(uint32_t budget_ms) {
    if(budget_ms && active && clock_api->monotonic_ms(clock_api->context)>=deadline)(void)off(NULL);
}
static bool quiesce(void) {
    if(claim){if(!off(NULL)||!gpio->release(gpio->context,claim))return false;claim=0;}
    started=false;failed=false;return true;
}
static void stop(void){(void)quiesce();}
static bool start(const risc_provider_dependency_v1 *deps,size_t n) {
    if(started || claim)return false;
    config=tw_config(deps,n,"generic,erm-gpio","gpio.bank",sizeof(*config));
    if(!config || config->count!=1 || config->active_high>1 || config->pull_up || !tw_pin(config->pins[0]))return false;
    gpio=tw_dep(deps,n,"platform.gpio",offsetof(garden_gpio_v1,deep_sleep_hold));
    clock_api=tw_dep(deps,n,"platform.clock",sizeof(*clock_api));
    if(!gpio || !gpio->claim || !gpio->write || !gpio->release || !tw_clock_valid(clock_api))return false;
    if(!gpio->claim(gpio->context,config->pins[0],true,!config->active_high,false,&claim))return false;
    started=true;active=failed=false;deadline=0;return true;
}
static const twatch_haptic_api_v1 api={1,sizeof(api),NULL,effect,off};
static const risc_driver_poll_v2 driver={.streams={.driver={2,sizeof(driver),"erm-haptic","haptic.effect",1,&api,start,stop,quiesce}},.poll=poll};
__attribute__((visibility("default"))) const risc_driver_v2 *t5_driver_get(uint32_t version){return version==2?&driver.streams.driver:NULL;}
