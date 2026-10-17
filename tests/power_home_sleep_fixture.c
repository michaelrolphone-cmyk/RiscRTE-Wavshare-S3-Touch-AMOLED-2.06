/* Actual shared Home sleep policy and Waveshare power provider. The modeled
 * native boundary enforces Runtime's zero-duration rule and terminal Deep. */
#include "hardware_model.h"
#ifndef POWER_PROVIDER_SOURCE
#define POWER_PROVIDER_SOURCE "../drivers/power_axp2101/driver.c"
#endif
#include POWER_PROVIDER_SOURCE
#define WATCH_ALARM_SLEEP_RESUME
#include "watch_alarm_sleep.h"
#include <setjmp.h>
static jmp_buf terminal;
static unsigned ordinary_light,timed_light,ordinary_deep,timed_deep,light_returns,restores,plans;
static uint32_t deadline,timer_wake=RISC_LIGHT_SLEEP_WAKE_TIMER;
static int32_t native_light(void *c,uint64_t token,bool high,risc_light_sleep_result_v1 *out) {
    (void)c;assert(token==1&&!high&&prepared);++ordinary_light;out->wake_cause=RISC_LIGHT_SLEEP_WAKE_GPIO;return 0;
}
static int32_t native_light_for(void *c,uint64_t token,bool high,uint32_t ms,risc_light_sleep_result_v1 *out) {
    (void)c;assert(token==1&&!high&&prepared);
    if(!ms||ms>RISC_TIMED_SLEEP_MAX_MS)return RISC_LIGHT_SLEEP_INVALID;
    ++timed_light;out->wake_cause=timer_wake;return 0;
}
static int32_t native_deep(void *c,uint64_t token,bool high) {
    (void)c;assert(token==1&&!high&&prepared);++ordinary_deep;longjmp(terminal,1);
}
static int32_t native_deep_for(void *c,uint64_t token,bool high,uint32_t ms) {
    (void)c;assert(token==1&&!high&&prepared);
    if(!ms||ms>RISC_TIMED_SLEEP_MAX_MS)return RISC_DEEP_SLEEP_INVALID;
    ++timed_deep;longjmp(terminal,1);
}
static bool panel_prepare(void *c){(void)c;return true;}
static int32_t panel_deep(void *c){(void)c;return 0;}
static bool panel_restore(void *c){(void)c;++restores;return true;}
static int32_t panel_restore_status(void *c){return panel_restore(c)?0:-1;}
static bool diagnostic(const char *s){(void)s;return true;}
static int32_t alarm_plan(void *c,alarm_sleep_v1 *out){
    (void)c;++plans;*out=(alarm_sleep_v1){.struct_size=sizeof(*out),.snapshot=plans,.rtc_seconds=1000,.deadline=deadline};return ALARM_OK;
}
static int32_t alarm_resume(void *c,const alarm_sleep_v1 *plan){(void)c;assert(plan->snapshot==plans);++light_returns;return ALARM_OK;}
static int32_t alarm_refresh(void *c){(void)c;return ALARM_OK;}
static const risc_display_power_api_v1 display_power={1,sizeof(display_power),NULL,panel_prepare,panel_restore,panel_deep,panel_restore_status};
static const risc_power_sleep_api_v1 power={1,sizeof(power),NULL,prepare_sleep,resume,light,deep,light_for,pending,deep_for,light_set,deep_set};
static const alarm_service_sleep_v1 alarm={.base={.api_version=1,.struct_size=sizeof(alarm),.prepare_sleep=alarm_plan,.refresh=alarm_refresh},.resume_sleep=alarm_resume};
static void setup_case(void){
    reset_model_();pin_levels_[0]=true;
    static tw_hw_i2c_device_v1 cfg;
    cfg=(tw_hw_i2c_device_v1){.struct_size=sizeof(cfg),.bus=i2c_config_,.address=0x34,.chip_id=0x4a,.irq=0,.irq_pull_up=1};
    hardware_.compatible="x-powers,axp2101";hardware_.config_type="peripheral.i2c";hardware_.config=&cfg;hardware_.config_size=sizeof(cfg);
    gpio_.light_sleep=native_light;gpio_.light_sleep_for=native_light_for;gpio_.deep_sleep=native_deep;gpio_.deep_sleep_for=native_deep_for;
    registers_[3]=0x4a;assert(start(deps_,4));
    ordinary_light=timed_light=ordinary_deep=timed_deep=light_returns=restores=plans=0;
}
static void run(unsigned mode,uint32_t alarm_deadline,uint32_t wake,bool deep_expected){
    setup_case();deadline=alarm_deadline;timer_wake=wake;
    if(!setjmp(terminal)){
        int result=watch_alarm_sleep_prepared(&display_power,&power,mode,&alarm.base,diagnostic);
        printf("mode=%u deadline=%u result=%d stage=%u detail=%d\n",mode,deadline,result,watch_sleep_stage,watch_sleep_detail);fflush(stdout);
        assert(!deep_expected&&result==WATCH_SLEEP_WOKE&&restores==1&&light_returns==1);
    }else{
        assert(deep_expected&&restores==0);
        if(deadline)assert(timed_deep==1&&!ordinary_deep);else assert(ordinary_deep==1&&!timed_deep);
        if(mode==PORTABLE_SLEEP_HYBRID)assert(timed_light==1&&light_returns==1&&plans==2);
        else assert(!ordinary_light&&!timed_light&&!light_returns&&plans==1);
    }
    assert(resume(NULL)&&quiesce());no_claims_();
}
int main(void){
    (void)watch_sleep_prepared;
    /* First case reproduces the periodic timer-to-Deep bounce without fix. */
    run(PORTABLE_SLEEP_HYBRID,0,RISC_LIGHT_SLEEP_WAKE_TIMER,true);
    run(PORTABLE_SLEEP_LIGHT,0,RISC_LIGHT_SLEEP_WAKE_GPIO,false);
    run(PORTABLE_SLEEP_DEEP,0,RISC_LIGHT_SLEEP_WAKE_TIMER,true);
    run(PORTABLE_SLEEP_DEEP,1005,RISC_LIGHT_SLEEP_WAKE_TIMER,true);
    run(PORTABLE_SLEEP_HYBRID,1600,RISC_LIGHT_SLEEP_WAKE_TIMER,true);
    run(PORTABLE_SLEEP_HYBRID,1005,RISC_LIGHT_SLEEP_WAKE_TIMER,false);
    run(PORTABLE_SLEEP_HYBRID,0,RISC_LIGHT_SLEEP_WAKE_GPIO,false);
    puts("Actual Home -> Waveshare power: untimed/timed Light/Deep, Hybrid transition, alarm and GPIO wake priority PASS");
}
