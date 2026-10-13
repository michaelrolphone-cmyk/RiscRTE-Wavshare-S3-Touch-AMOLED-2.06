/* Board-selected AXP2101 ALDO2 output: schematic DSI_PWR_EN via R10.
 * The public capability is generic power.rail@1. No battery-gauge API, app
 * or firmware-native pin knowledge is required. Only 0x90 bit1 and 0x93 low
 * five bits are writable; charging, DCDC, other LDOs and IRQs stay untouched.
 * Registers follow the vendor-bundled XPowersLib 0.2.6. Both VCI and VDDIO
 * on this panel are 3.3V; this provider selects the matching 3.3V enable level.
 * I2C device claims are scoped to one synchronous operation so the battery
 * provider can use the same PMIC without an undocumented combined API. */
#include "DriverSupport.h"
#include "RiscPowerRailV1.h"
#include "RiscI2cFunctionV1.h"
#include "ProviderLog.h"
#include <stdio.h>
#define PMIC_ADDRESS 0x34u
#define PMIC_ID 0x4au
#define ENABLE_REG 0x90u
#define VOLTAGE_REG 0x93u
#define ENABLE_MASK 0x02u
#define VOLTAGE_MASK 0x1fu
#define VOLTAGE_3300 28u
static const risc_i2c_bus_api_v1 *bus;
static const risc_platform_clock_api_v1 *clock_api;
static uint64_t session;
static const risc_hw_i2c_function_v1 *function;
static bool active;
static bool begin_session(void) {
    return bus && !session && bus->claim_device(bus->context,function->address,&session) && session;
}
static bool end_session(void) {
    if(!session)return true;
    if(!bus->release_device(bus->context,session))return false;
    session=0;return true;
}
static bool read8(uint8_t reg,uint8_t *value) {
    return bus->transact(bus->context,session,&reg,1,value,1,30);
}
static bool write8(uint8_t reg,uint8_t value) {
    uint8_t bytes[]={reg,value};
    return bus->transact(bus->context,session,bytes,2,NULL,0,30);
}
static bool snapshot(uint8_t *enable,uint8_t *voltage) {
    uint8_t id=0;
    return read8(3,&id) && id==PMIC_ID && read8(ENABLE_REG,enable) && read8(VOLTAGE_REG,voltage);
}
static void log_state(const char *stage,uint8_t enable,uint8_t voltage) {
    char line[128];
    snprintf(line,sizeof(line),"PANEL_POWER stage=%s aldo2_enabled=%u configured_mv=%u reg90=0x%02x reg93=0x%02x",
        stage,!!(enable&ENABLE_MASK),500u+100u*(voltage&VOLTAGE_MASK),enable,voltage);
    provider_log(line);
}
static bool get_info(void *context,risc_power_rail_info_v1 *out) {
    (void)context;
    if(!active || !out || out->struct_size<sizeof(*out))return false;
    *out=(risc_power_rail_info_v1){.struct_size=sizeof(*out)};
    if(!begin_session())return false;
    uint8_t enable=0,voltage=0;
    bool ok=snapshot(&enable,&voltage);
    if(!end_session())return false;
    if(!ok)return false;
    out->enabled=(enable&ENABLE_MASK)!=0;
    out->configured_millivolts=500u+100u*(voltage&VOLTAGE_MASK);
    out->configuration_verified=true;return true;
}
static bool set_enabled(void *context,bool wanted) {
    (void)context;
    if(!active || !begin_session())return false;
    uint8_t before_enable=0,before_voltage=0,after_enable=0,after_voltage=0;
    bool ok=snapshot(&before_enable,&before_voltage);
    if(ok)log_state("before",before_enable,before_voltage);
    uint8_t target_enable=wanted?(before_enable|ENABLE_MASK):(before_enable&~ENABLE_MASK);
    uint8_t target_voltage=wanted?((before_voltage&~VOLTAGE_MASK)|VOLTAGE_3300):before_voltage;
    if(ok && wanted && target_voltage!=before_voltage) {
        /* Do not change an enabled rail's setpoint under the held-reset load.
         * Mask this channel only, program, then restore its enabled state. */
        if(before_enable&ENABLE_MASK)ok=write8(ENABLE_REG,before_enable&~ENABLE_MASK);
        if(ok)ok=write8(VOLTAGE_REG,target_voltage);
    }
    if(ok && (target_enable!=before_enable || (wanted && target_voltage!=before_voltage)))
        ok=write8(ENABLE_REG,target_enable);
    if(ok)clock_api->sleep_ms(clock_api->context,10);
    if(ok)ok=snapshot(&after_enable,&after_voltage);
    if(ok) {
        log_state("after",after_enable,after_voltage);
        ok=after_enable==target_enable && after_voltage==target_voltage;
    }
    bool released=end_session();
    if(!ok || !released)provider_log("PANEL_POWER result=failed operation=configure-or-readback");
    else provider_log("PANEL_POWER result=verified source=pmic-registers not=load-voltage-measurement");
    return ok&&released;
}
static bool quiesce(void) {return end_session();}
static void stop(void) {
    if(!quiesce())return;
    /* Do not switch off unrelated board power during graph teardown. The
     * consumer's display/reset sequence handles the load; retain rail policy. */
    active=false;bus=NULL;clock_api=NULL;
}
static bool start(const risc_provider_dependency_v1 *deps,size_t n) {
    if(active || session)return false;
    function=tw_config(deps,n,"x-powers,axp2101-aldo2","peripheral.i2c-function",sizeof(*function));
    if(!function || !function->parent_instance_id || function->function_id!=2 ||
       function->address!=PMIC_ADDRESS || function->chip_id!=PMIC_ID || function->reserved ||
       !tw_bus_limit(&function->bus,RISC_HW_BUS_I2C,400000))return false;
    bus=tw_dep(deps,n,"i2c.bus",sizeof(*bus));
    clock_api=tw_dep(deps,n,"platform.clock",sizeof(*clock_api));
    if(!tw_i2c_valid(bus) || !tw_clock_valid(clock_api) || !begin_session())return false;
    uint8_t enable=0,voltage=0;
    bool ok=snapshot(&enable,&voltage);
    if(ok)log_state("discovered",enable,voltage);
    bool released=end_session();
    if(!ok || !released){provider_log("PANEL_POWER result=failed operation=probe-pmic");return false;}
    /* Discovery does not modify the rail. The display asserts reset first. */
    active=true;return true;
}
static const risc_power_rail_api_v1 api={1,sizeof(api),NULL,get_info,set_enabled};
static const risc_driver_v2 descriptor={2,sizeof(descriptor),"axp2101-aldo2-rail",RISC_POWER_RAIL_CAPABILITY,1,&api,start,stop,quiesce};
__attribute__((visibility("default"))) const risc_driver_v2 *t5_driver_get(uint32_t abi) {return abi==2?&descriptor:NULL;}
