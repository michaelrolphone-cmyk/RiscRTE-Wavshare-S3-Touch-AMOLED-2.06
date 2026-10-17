#pragma once
#include <stdint.h>
#include <stdbool.h>
#include <RiscTimedSleepV1.h>
#ifdef __cplusplus
extern "C" {
#endif
enum wave_home_case {
    WAVE_HYBRID_ORDINARY, WAVE_HYBRID_TIMED, WAVE_HYBRID_SET,
    WAVE_HYBRID_SET_TIMED, WAVE_ALARM_DUE, WAVE_GPIO_WAKE, WAVE_LIGHT_UNTIMED,
    WAVE_HOME_CASE_COUNT
};
typedef struct wave_home_observation {
    int32_t result, detail;
    unsigned stage, plans, alarm_resumes, restores, deep_prepares, motion_resumes;
} wave_home_observation;
void wave_home_run(unsigned scenario);
wave_home_observation wave_home_observe(void);
void wave_home_finish(void);
int32_t wave_native_light(uint32_t ms, bool wake_set, risc_light_sleep_result_v1 *out);
int32_t wave_native_deep(uint32_t ms, bool wake_set);
#ifdef __cplusplus
}
#endif
