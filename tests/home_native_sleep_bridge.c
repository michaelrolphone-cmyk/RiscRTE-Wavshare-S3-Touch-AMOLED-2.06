/* Real shared Home policy and real Waveshare .53 power entry, bridged to
 * Runtime's native CPU/serial implementation. Panel, alarm and board I/O are
 * modeled; no device is accessed and no storage namespace is admitted. */
#include <stdbool.h>
#include "home_native_sleep_bridge.h"
#include "hardware_model.h"
#include "../drivers/power_axp2101/driver.c"
#define WATCH_ALARM_SLEEP_RESUME
#include "watch_alarm_sleep.h"
static unsigned scenario_;
static wave_home_observation observed_;
static int32_t native_light(void *c,uint64_t token,bool high,risc_light_sleep_result_v1 *out) {
    (void)c;assert(token==1&&!high&&prepared);return wave_native_light(0,false,out);
}
static int32_t native_light_for(void *c,uint64_t token,bool high,uint32_t ms,risc_light_sleep_result_v1 *out) {
    (void)c;assert(token==1&&!high&&prepared&&ms);return wave_native_light(ms,false,out);
}
static int32_t native_light_set(void *c,uint64_t token,bool high,uint32_t ms,risc_light_sleep_result_v1 *out) {
    (void)c;assert(token==1&&!high&&prepared);return wave_native_light(ms,true,out);
}
static int32_t native_deep(void *c,uint64_t token,bool high) {
    (void)c;assert(token==1&&!high&&prepared);return wave_native_deep(0,false);
}
static int32_t native_deep_for(void *c,uint64_t token,bool high,uint32_t ms) {
    (void)c;assert(token==1&&!high&&prepared&&ms);return wave_native_deep(ms,false);
}
static int32_t native_deep_set(void *c,uint64_t token,bool high,uint32_t ms) {
    (void)c;assert(token==1&&!high&&prepared);return wave_native_deep(ms,true);
}
static bool panel_prepare(void *c){(void)c;return true;}
static int32_t panel_deep(void *c){(void)c;++observed_.deep_prepares;return 0;}
static bool panel_restore(void *c){(void)c;++observed_.restores;return true;}
static int32_t panel_restore_status(void *c){return panel_restore(c)?0:-1;}
static bool diagnostic(const char *s){(void)s;return true;}
static int32_t alarm_plan(void *c,alarm_sleep_v1 *out){
    (void)c;++observed_.plans;
    if(scenario_==WAVE_ALARM_DUE && observed_.plans==2)return ALARM_BUSY;
    const uint32_t deadline=(scenario_==WAVE_HYBRID_TIMED || scenario_==WAVE_HYBRID_SET_TIMED)?1600:0;
    *out=(alarm_sleep_v1){.struct_size=sizeof(*out),.snapshot=observed_.plans,.rtc_seconds=1000,.deadline=deadline};return ALARM_OK;
}
static int32_t alarm_resume(void *c,const alarm_sleep_v1 *plan){
    (void)c;assert(plan->snapshot==observed_.plans);++observed_.alarm_resumes;return ALARM_OK;
}
static int32_t alarm_refresh(void *c){(void)c;return ALARM_OK;}
static bool motion_prepare(void *c){(void)c;return true;}
static bool motion_pending(void *c,bool *pending){(void)c;*pending=false;return true;}
static bool motion_resume(void *c){(void)c;++observed_.motion_resumes;return true;}
static const risc_display_power_api_v1 panel={1,sizeof(panel),NULL,panel_prepare,panel_restore,panel_deep,panel_restore_status};
static const risc_power_sleep_api_v1 power={1,sizeof(power),NULL,prepare_sleep,resume,light,deep,light_for,pending,deep_for,light_set,deep_set};
static const alarm_service_sleep_v1 alarm={.base={.api_version=1,.struct_size=sizeof(alarm),.prepare_sleep=alarm_plan,.refresh=alarm_refresh},.resume_sleep=alarm_resume};
static const twatch_motion_api_v1 motion={.api_version=TWATCH_MOTION_API_V1,.struct_size=sizeof(motion),.prepare_wake=motion_prepare,.wake_pending=motion_pending,.resume_wake=motion_resume};
void wave_home_run(unsigned scenario){
    (void)watch_sleep_prepared;(void)watch_alarm_sleep_prepared;
    assert(scenario<WAVE_HOME_CASE_COUNT);scenario_=scenario;
    observed_=(wave_home_observation){.result=-99};
    reset_model_();pin_levels_[0]=true;
    static tw_hw_i2c_device_v1 cfg;
    cfg=(tw_hw_i2c_device_v1){.struct_size=sizeof(cfg),.bus=i2c_config_,.address=0x34,.chip_id=0x4a,.irq=0,.irq_pull_up=1};
    hardware_.compatible="x-powers,axp2101";hardware_.config_type="peripheral.i2c";hardware_.config=&cfg;hardware_.config_size=sizeof(cfg);
    gpio_.light_sleep=native_light;gpio_.light_sleep_for=native_light_for;gpio_.light_sleep_set=native_light_set;
    gpio_.deep_sleep=native_deep;gpio_.deep_sleep_for=native_deep_for;gpio_.deep_sleep_set=native_deep_set;
    registers_[3]=0x4a;assert(start(deps_,4));
    const twatch_motion_api_v1 *m=(scenario==WAVE_HYBRID_SET || scenario==WAVE_HYBRID_SET_TIMED)?&motion:NULL;
    const unsigned mode=scenario==WAVE_LIGHT_UNTIMED?PORTABLE_SLEEP_LIGHT:PORTABLE_SLEEP_HYBRID;
    observed_.result=watch_alarm_sleep_motion_prepared(&panel,&power,m,mode,&alarm.base,diagnostic);
}
wave_home_observation wave_home_observe(void){
    observed_.stage=watch_sleep_stage;observed_.detail=watch_sleep_detail;return observed_;
}
void wave_home_finish(void){assert(resume(NULL)&&quiesce());no_claims_();}
