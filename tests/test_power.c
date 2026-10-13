#include "hardware_model.h"
#include "../drivers/power_axp2101/driver.c"
#ifndef TEST_KEY_PIN
#define TEST_KEY_PIN 10
#define TEST_KEY_HIGH 1
#endif
static tw_hw_i2c_device_v1 cfg;
static uint64_t slept_token;static bool slept_high;static unsigned slept_ms;static int32_t sleep_result;
static int32_t fake_light(void *ctx,uint64_t token,bool high,uint32_t ms,risc_light_sleep_result_v1 *out) {
    (void)ctx;slept_token=token;slept_high=high;slept_ms=ms;out->wake_cause=RISC_LIGHT_SLEEP_WAKE_GPIO;return sleep_result;
}
static int32_t fake_deep(void *ctx,uint64_t token,bool high,uint32_t ms) {
    (void)ctx;slept_token=token;slept_high=high;slept_ms=ms;return RISC_DEEP_SLEEP_UNSUPPORTED;
}
static void setup(void) {
    reset_model_();memset(pin_levels_,0,sizeof(pin_levels_));sleep_result=RISC_LIGHT_SLEEP_OK;pin_levels_[TEST_KEY_PIN]=!TEST_KEY_HIGH;
    cfg=(tw_hw_i2c_device_v1){.struct_size=sizeof(cfg),.bus=i2c_config_,.address=0x34,.chip_id=0x4a,.irq=TEST_KEY_PIN,.irq_active_high=TEST_KEY_HIGH,.irq_pull_up=!TEST_KEY_HIGH};
    hardware_.compatible="x-powers,axp2101";hardware_.config_type="peripheral.i2c";hardware_.config=&cfg;hardware_.config_size=sizeof(cfg);
    gpio_.light_sleep_for=fake_light;gpio_.deep_sleep_for=fake_deep;gpio_.light_sleep_set=fake_light;gpio_.deep_sleep_set=fake_deep;
    registers_[3]=0x4a;registers_[0x30]=0xa0;
    registers_[0]=0x28;registers_[1]=0;registers_[0x18]=0x0a;registers_[0x68]=1;
    registers_[0x34]=0x0f;registers_[0x35]=0xa0;registers_[0xa4]=75;
}
static bool release_failure;
static bool release_test(void *c,uint64_t token) {
 if(release_failure)return false;
 return bus_release_(c,token);
}
int main(void) {
    setup();assert(start(deps_,4));assert(writes_==1&&write_registers_[0]==0x30&&registers_[0x30]==0xa1);
    assert(!bus_token_);
    uint64_t rail_session=0;assert(bus_claim_(NULL,0x34,&rail_session));assert(bus_release_(NULL,rail_session));
    risc_battery_sample_v1 value;assert(read_sample(NULL,&value));assert(value.millivolts==4000&&value.percent==75);
    assert(!bus_token_);assert(value.flags&PORTABLE_POWER_STATUS_VALID);assert(value.flags&PORTABLE_POWER_CHARGER_ENABLED);
    registers_[0xa4]=0;assert(read_sample(NULL,&value)&&value.percent==0);registers_[0xa4]=100;assert(read_sample(NULL,&value)&&value.percent==100);
    registers_[0xa4]=255;assert(read_sample(NULL,&value)&&value.percent==255&&(value.flags&RISC_BATTERY_PROFILE_MISSING));
    registers_[0xa4]=50;registers_[0x17]=8;assert(read_sample(NULL,&value)&&value.percent==255);registers_[0x17]=0;
    fail_transaction_=transactions_+2;assert(!read_sample(NULL,&value)&&value.percent==255);fail_transaction_=0;
    bool is_pending=true;assert(pending(NULL,&is_pending)&&!is_pending);
    uint32_t events=99;assert(key_events(NULL,&events)&&!events);
    pin_levels_[TEST_KEY_PIN]=TEST_KEY_HIGH;tick_=100;assert(key_events(NULL,&events)&&!events);tick_=120;assert(key_events(NULL,&events)&&!events);
    assert(!prepare_sleep(NULL));pin_levels_[TEST_KEY_PIN]=!TEST_KEY_HIGH;tick_=200;assert(key_events(NULL,&events)&&!events);tick_=220;assert(key_events(NULL,&events)&&events==2);
    pin_levels_[TEST_KEY_PIN]=TEST_KEY_HIGH;tick_=300;assert(key_events(NULL,&events));tick_=320;assert(key_events(NULL,&events));tick_=920;assert(key_events(NULL,&events)&&events==1);
    pin_levels_[TEST_KEY_PIN]=!TEST_KEY_HIGH;tick_=950;assert(key_events(NULL,&events));tick_=970;assert(key_events(NULL,&events)&&!events);
    // Completed press between application reads must survive scheduler sampling.
    pin_levels_[TEST_KEY_PIN]=TEST_KEY_HIGH;tick_=1100;power_poll(1);tick_=1120;power_poll(1);
    pin_levels_[TEST_KEY_PIN]=!TEST_KEY_HIGH;tick_=1180;power_poll(1);tick_=1200;power_poll(1);
    tick_=1600;assert(key_events(NULL,&events)&&events==2);
    assert(key_events(NULL,&events)&&!events);
    // Long presses are latched once; their release is never a second short.
    pin_levels_[TEST_KEY_PIN]=TEST_KEY_HIGH;tick_=1700;power_poll(1);tick_=1720;power_poll(1);tick_=2320;power_poll(1);
    pin_levels_[TEST_KEY_PIN]=!TEST_KEY_HIGH;tick_=2350;power_poll(1);tick_=2370;power_poll(1);
    assert(key_events(NULL,&events)&&events==1);assert(key_events(NULL,&events)&&!events);
    risc_light_sleep_result_v1 result={.struct_size=sizeof(result)};
    assert(light_for(NULL,100,&result)==RISC_LIGHT_SLEEP_INVALID);assert(prepare_sleep(NULL));
    assert(light_for(NULL,100,&result)==RISC_LIGHT_SLEEP_OK);assert(slept_token==TEST_KEY_PIN+1&&slept_high==!!TEST_KEY_HIGH&&slept_ms==100);
    assert(resume(NULL));assert(light_for(NULL,100,&result)==RISC_LIGHT_SLEEP_INVALID);
    assert(prepare_sleep(NULL));assert(light_set(NULL,200,&result)==RISC_LIGHT_SLEEP_OK&&slept_ms==200);
    assert(deep_set(NULL,300)==RISC_DEEP_SLEEP_UNSUPPORTED&&slept_ms==300&&slept_high==!!TEST_KEY_HIGH);
    assert(quiesce());no_claims_();
    for(unsigned n=1;n<=3;n++){setup();fail_transaction_=n;assert(!start(deps_,4));no_claims_();}
    setup();fail_gpio_=1;assert(!start(deps_,4));no_claims_();
    setup();cfg.irq=-1;assert(!start(deps_,4));no_claims_();
    setup();assert(start(deps_,4));bus_.release_device=release_test;release_failure=true;
    assert(!read_sample(NULL,&value));assert(claim&&bus_token_);assert(!quiesce());
    release_failure=false;assert(quiesce());bus_.release_device=bus_release_;no_claims_();
    setup();assert(start(deps_,4));assert(prepare_sleep(NULL));sleep_result=RISC_LIGHT_SLEEP_RETAINED;
    assert(light_for(NULL,100,&result)==RISC_LIGHT_SLEEP_RETAINED);assert(!read_sample(NULL,&value));assert(!quiesce());
    puts("AXP2101: battery admission/charger preservation/active-high key/sleep/failure cleanup PASS");return 0;
}
