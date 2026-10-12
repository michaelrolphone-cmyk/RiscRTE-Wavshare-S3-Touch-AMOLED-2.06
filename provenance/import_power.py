"""Extract existing battery decoding and supply Waveshare key/sleep integration."""
from pathlib import Path
import json
V=Path(__file__).resolve().parents[1];W=V/'.source/twatch'
s=(W/'drivers/twatch_pmu/driver.c').read_text();defines=s[s.index('#define AXP_STATUS1'):s.index('static const risc_i2c_bus_api_v1')]
sample=s[s.index('static bool read_sample('):s.index('static bool last_error(')].replace('    error[0] = 0;\n','').replace('        set_error("AXP2101 battery read failed");\n','').replace('if (!started)','if (!started || retained)')
preamble='''/* AXP2101 telemetry and active-high SYS_OUT power-key/sleep provider.
 * Battery cell policy and factory rail settings are left unchanged. The only
 * PMIC write enables VBAT measurement; no charge voltage/current/TS/model writes. */
#include "DriverSupport.h"
#include "twatch_caps.h"
#include "PortablePowerStatus.h"
'''+defines+'''
static const risc_i2c_bus_api_v1 *bus;
static const risc_gpio_bank_api_v1 *gpio_api;
static const risc_platform_clock_api_v1 *clock_api;
static const tw_hw_i2c_device_v1 *config;
static uint64_t claim, key_claim, edge_at, pressed_at;
static bool started, prepared, retained, raw_key, stable_key, long_sent;
static bool read_reg(uint8_t reg,uint8_t *out,size_t n) {
    return bus->transact(bus->context,claim,&reg,1,out,n,30);
}
static bool write_reg(uint8_t reg,uint8_t value) {
    uint8_t bytes[]={reg,value};
    return bus->transact(bus->context,claim,bytes,2,NULL,0,30);
}
static bool pending(void *c,bool *out) {
    (void)c;if(!started || retained || !out)return false;
    bool level;if(!gpio_api->read(gpio_api->context,key_claim,&level))return false;
    *out=level==!!config->irq_active_high;return true;
}
static bool key_events(void *c,uint32_t *events) {
    if(!events)return false;*events=0;
    bool value;if(!pending(c,&value))return false;
    uint64_t now=clock_api->monotonic_ms(clock_api->context);
    if(value!=raw_key){raw_key=value;edge_at=now;}
    if(stable_key!=raw_key && now-edge_at>=20) {
        stable_key=raw_key;
        if(stable_key){pressed_at=now;long_sent=false;}
        else if(!long_sent)*events=2;
    }
    if(stable_key && !long_sent && now-pressed_at>=600){long_sent=true;*events=1;}
    return true;
}
static bool prepare_sleep(void *c) {
    bool key;if(!pending(c,&key) || key)return false;prepared=true;return true;
}
static bool resume(void *c) {(void)c;if(!started || retained)return false;prepared=false;return true;}
static int32_t result_code(int32_t rc) {
    if(rc==RISC_LIGHT_SLEEP_RETAINED)retained=true;
    return rc;
}
static int32_t light_for(void *c,uint32_t ms,risc_light_sleep_result_v1 *out) {
    (void)c;
    if(!started || retained || !prepared || !out || ms>RISC_TIMED_SLEEP_MAX_MS)return RISC_LIGHT_SLEEP_INVALID;
    if(gpio_api->struct_size<RISC_GPIO_BANK_LIGHT_SLEEP_FOR_V1_SIZE || !gpio_api->light_sleep_for)return RISC_LIGHT_SLEEP_UNSUPPORTED;
    return result_code(gpio_api->light_sleep_for(gpio_api->context,key_claim,config->irq_active_high,ms,out));
}
static int32_t light(void *c,risc_light_sleep_result_v1 *out) {return light_for(c,0,out);}
static int32_t deep_for(void *c,uint32_t ms) {
    (void)c;
    if(!started || retained || !prepared || ms>RISC_TIMED_SLEEP_MAX_MS)return RISC_DEEP_SLEEP_INVALID;
    if(gpio_api->struct_size<RISC_GPIO_BANK_DEEP_SLEEP_FOR_V1_SIZE || !gpio_api->deep_sleep_for)return RISC_DEEP_SLEEP_UNSUPPORTED;
    int32_t rc=gpio_api->deep_sleep_for(gpio_api->context,key_claim,config->irq_active_high,ms);
    if(rc==RISC_DEEP_SLEEP_RETAINED)retained=true;return rc;
}
static int32_t deep(void *c) {return deep_for(c,0);}
static int32_t light_set(void *c,uint32_t ms,risc_light_sleep_result_v1 *out) {
    (void)c;
    if(!started || retained || !prepared || !out || ms>RISC_TIMED_SLEEP_MAX_MS)return RISC_LIGHT_SLEEP_INVALID;
    if(gpio_api->struct_size<RISC_GPIO_BANK_LIGHT_SLEEP_SET_V1_SIZE || !gpio_api->light_sleep_set)return RISC_LIGHT_SLEEP_UNSUPPORTED;
    return result_code(gpio_api->light_sleep_set(gpio_api->context,key_claim,config->irq_active_high,ms,out));
}
static int32_t deep_set(void *c,uint32_t ms) {
    (void)c;
    if(!started || retained || !prepared || ms>RISC_TIMED_SLEEP_MAX_MS)return RISC_DEEP_SLEEP_INVALID;
    if(gpio_api->struct_size<RISC_GPIO_BANK_DEEP_SLEEP_SET_V1_SIZE || !gpio_api->deep_sleep_set)return RISC_DEEP_SLEEP_UNSUPPORTED;
    int32_t rc=gpio_api->deep_sleep_set(gpio_api->context,key_claim,config->irq_active_high,ms);
    if(rc==RISC_DEEP_SLEEP_RETAINED)retained=true;return rc;
}
'''
end='''
static bool quiesce(void) {
    if(retained)return false;
    if(claim){if(!bus->release_device(bus->context,claim))return false;claim=0;}
    if(key_claim){if(!gpio_api->release(gpio_api->context,key_claim))return false;key_claim=0;}
    started=prepared=false;bus=NULL;gpio_api=NULL;clock_api=NULL;return true;
}
static bool start(const risc_provider_dependency_v1 *deps,size_t n) {
    if(started || claim || key_claim || retained)return false;
    config=tw_config(deps,n,"x-powers,axp2101","peripheral.i2c",sizeof(*config));
    if(!tw_i2c_config_valid(config) || config->chip_id!=0x4a || config->irq<0 || !config->irq_active_high || config->irq_pull_up)return false;
    bus=tw_dep(deps,n,"i2c.bus",sizeof(*bus));
    gpio_api=tw_dep(deps,n,"gpio.bank",offsetof(risc_gpio_bank_api_v1,light_sleep));
    clock_api=tw_dep(deps,n,"platform.clock",sizeof(*clock_api));
    if(!tw_i2c_valid(bus) || !tw_gpio_valid(gpio_api) || !tw_clock_valid(clock_api))return false;
    if(!bus->claim_device(bus->context,config->address,&claim) ||
       !gpio_api->claim(gpio_api->context,config->irq,RISC_GPIO_INPUT,&key_claim)){(void)quiesce();return false;}
    uint8_t id,adc;
    if(!read_reg(3,&id,1) || id!=config->chip_id || !read_reg(AXP_ADC_EN,&adc,1) ||
       !write_reg(AXP_ADC_EN,adc|1) || !gpio_api->read(gpio_api->context,key_claim,&raw_key)) {
        (void)quiesce();return false;
    }
    raw_key=raw_key==!!config->irq_active_high;stable_key=raw_key;
    edge_at=pressed_at=clock_api->monotonic_ms(clock_api->context);long_sent=false;
    prepared=false;started=true;return true;
}
static void stop(void){(void)quiesce();}
static const twatch_pmu_api_v1 api={
    {1,sizeof(api),NULL,read_sample},key_events,prepare_sleep,resume,light,deep,light_for,pending,deep_for,light_set,deep_set};
static const risc_driver_v2 descriptor={2,sizeof(descriptor),"waveshare-power","board.battery",1,&api,start,stop,quiesce};
__attribute__((visibility("default"))) const risc_driver_v2 *t5_driver_get(uint32_t version){return version==2?&descriptor:NULL;}
'''
(V/'drivers/power_axp2101/driver.c').write_text(preamble+sample+end)
m={'type':'driver','id':'waveshare-power','version':'0.1.0','driver_abi':2,'architecture':'xtensa-esp32s3','file_name':'driver.elf','requires':[{'capability':x,'api':1} for x in ['hardware.device','i2c.bus','gpio.bank','platform.clock']],'provides':[{'capability':'board.battery','api':1}],'hardware_compatibility':[{'compatible':'x-powers,axp2101','revisions':['unspecified'],'config_type':'peripheral.i2c','config_version':1}],'physical_verification':'pending'}
(V/'drivers/power_axp2101/manifest.json').write_text(json.dumps(m,indent=2)+'\n')
