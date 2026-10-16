/* Use the actual provider with strict Runtime timer-contract callbacks. The
 * released provider incorrectly sent zero to the timer suffix, hiding behind
 * the permissive fake in test_power.c. */
#define main inherited_power_main
#include "test_power.c"
#undef main
static unsigned plain_light_calls,plain_deep_calls,timed_light_calls,timed_deep_calls;
static int32_t strict_timed_light(void *c,uint64_t t,bool h,uint32_t ms,risc_light_sleep_result_v1 *out) {
    ++timed_light_calls;
    if(!ms || ms>RISC_TIMED_SLEEP_MAX_MS)return RISC_LIGHT_SLEEP_INVALID;
    return fake_light(c,t,h,ms,out);
}
static int32_t strict_timed_deep(void *c,uint64_t t,bool h,uint32_t ms) {
    ++timed_deep_calls;
    if(!ms || ms>RISC_TIMED_SLEEP_MAX_MS)return RISC_DEEP_SLEEP_INVALID;
    return fake_deep(c,t,h,ms);
}
static int32_t plain_light(void *c,uint64_t t,bool h,risc_light_sleep_result_v1 *out) {
    ++plain_light_calls;return fake_light(c,t,h,0,out);
}
static int32_t plain_deep(void *c,uint64_t t,bool h) {
    ++plain_deep_calls;return fake_deep(c,t,h,0);
}
int main(void) {
    setup();gpio_.light_sleep=plain_light;gpio_.deep_sleep=plain_deep;
    gpio_.light_sleep_for=strict_timed_light;gpio_.deep_sleep_for=strict_timed_deep;
    assert(start(deps_,4)&&prepare_sleep(NULL));
    risc_light_sleep_result_v1 out={.struct_size=sizeof(out)};
    assert(light(NULL,&out)==RISC_LIGHT_SLEEP_OK);
    assert(plain_light_calls==1&&timed_light_calls==0&&slept_ms==0);
    assert(deep(NULL)==RISC_DEEP_SLEEP_UNSUPPORTED);
    assert(plain_deep_calls==1&&timed_deep_calls==0&&slept_ms==0);
    assert(light_for(NULL,17,&out)==0&&timed_light_calls==1&&slept_ms==17);
    assert(deep_for(NULL,23)==RISC_DEEP_SLEEP_UNSUPPORTED&&timed_deep_calls==1&&slept_ms==23);
    assert(light_for(NULL,0,&out)==RISC_LIGHT_SLEEP_INVALID);
    assert(deep_for(NULL,0)==RISC_DEEP_SLEEP_INVALID);
    assert(light_set(NULL,0,&out)==0&&slept_ms==0);
    assert(deep_set(NULL,0)==RISC_DEEP_SLEEP_UNSUPPORTED&&slept_ms==0);
    /* Untimed calls must still work with an older table ending before timers. */
    gpio_.struct_size=RISC_GPIO_BANK_DEEP_SLEEP_V1_SIZE;
    assert(light(NULL,&out)==0&&plain_light_calls==2);
    assert(deep(NULL)==RISC_DEEP_SLEEP_UNSUPPORTED&&plain_deep_calls==2);
    assert(light_for(NULL,17,&out)==RISC_LIGHT_SLEEP_UNSUPPORTED);
    assert(deep_for(NULL,23)==RISC_DEEP_SLEEP_UNSUPPORTED);
    gpio_.struct_size=sizeof(gpio_);gpio_.light_sleep=NULL;gpio_.deep_sleep=NULL;
    assert(light(NULL,&out)==RISC_LIGHT_SLEEP_UNSUPPORTED);
    assert(deep(NULL)==RISC_DEEP_SLEEP_UNSUPPORTED);
    assert(quiesce());no_claims_();
    puts("Power untimed/timed/set: zero never enters timer suffix; legacy callbacks and bounds PASS");
}
