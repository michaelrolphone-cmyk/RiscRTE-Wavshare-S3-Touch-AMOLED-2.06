/* QMI8658C motion.accel@1. Register/tap protocol derived from the MIT-licensed
 * SensorLib bundled with Waveshare b099739. No application policy or board pins.
 * The chip owns detection; wake observation never acknowledges its interrupt. */
#include "DriverSupport.h"
#include "PortableMotionTap.h"
#define WHOAMI 0x00u
#define CTRL1 0x02u
#define CTRL2 0x03u
#define CTRL5 0x06u
#define CTRL7 0x08u
#define CTRL8 0x09u
#define CTRL9 0x0au
#define STATUS_INT 0x2du
#define STATUS0 0x2eu
#define STATUS1 0x2fu
#define ACCEL 0x35u
#define TAP_STATUS 0x59u
#define TAP_PROFILE 3u
static const risc_i2c_bus_api_v1 *bus;
static const risc_gpio_bank_api_v1 *gpio;
static const risc_platform_clock_api_v1 *clock_api;
static const tw_hw_i2c_device_v1 *config;
static uint64_t claim,irq;
static bool started,changed,saved_valid,enrolled,observing,retained;
static uint8_t saved[5];
static uint16_t threshold=800;
static uint32_t error;
static const uint8_t saved_regs[]={CTRL1,CTRL2,CTRL5,CTRL7,CTRL8};
static bool read_regs(uint8_t reg,uint8_t *out,size_t n) {
    return !retained && bus && claim && bus->transact(bus->context,claim,&reg,1,out,n,20);
}
static bool write_regs(uint8_t reg,const uint8_t *bytes,size_t n) {
    if(retained || !bus || !claim || !bytes || !n || n>8)return false;
    uint8_t tx[9];tx[0]=reg;memcpy(tx+1,bytes,n);
    return bus->transact(bus->context,claim,tx,n+1,NULL,0,20);
}
static bool put(uint8_t reg,uint8_t value){return write_regs(reg,&value,1);}
static bool command(uint8_t command_id) {
    if(!put(CTRL9,command_id))return false;
    for(unsigned phase=0;phase<2;phase++) {
        uint64_t start=clock_api->monotonic_ms(clock_api->context);
        bool done=false;
        for(unsigned i=0;i<200;i++) {
            uint8_t status=0;
            if(!read_regs(STATUS_INT,&status,1))return false;
            if(!!(status&0x80u)==!phase){done=true;break;}
            if(clock_api->monotonic_ms(clock_api->context)-start>=200u)break;
            clock_api->sleep_ms(clock_api->context,1);
        }
        if(!done){error=2;return false;}
        if(!phase && !put(CTRL9,0))return false;
    }
    return true;
}
static bool sample(void *context,twatch_accel_sample_v1 *out) {
    (void)context;if(!started || !out || retained || (changed&&!observing))return false;
    uint8_t bytes[6];if(!read_regs(ACCEL,bytes,sizeof(bytes)))return false;
    int16_t values[3];
    for(unsigned i=0;i<3;i++) {
        uint16_t bits=(uint16_t)bytes[i*2]|((uint16_t)bytes[i*2+1]<<8);
        int32_t raw=(bits&0x8000u)?(int32_t)bits-65536:bits;
        values[i]=(int16_t)(raw*1000/8192); /* Fixed ±4 g, unit milli-g. */
    }
    *out=(twatch_accel_sample_v1){values[0],values[1],values[2]};return true;
}
static bool chip_id(void *context,uint8_t *out) {
    (void)context;return started && !retained && out && read_regs(WHOAMI,out,1);
}
static bool tap_info(void *context,twatch_tap_info_v1 *out) {
    (void)context;if(!started || !out || retained)return false;
    *out=(twatch_tap_info_v1){sizeof(*out),TAP_PROFILE,100,4000,800};return true;
}
static bool tap_configure(void *context,uint16_t value) {
    (void)context;if(!started || changed || enrolled || retained || value<100 || value>4000)return false;
    threshold=value;return true;
}
static bool restore(void *context) {
    (void)context;if(retained)return false;
    if(changed) {
        /* Restore the peripheral before withdrawing its wake enrollment. */
        if(!saved_valid || !put(CTRL7,0) || !put(CTRL8,0x80) || !put(CTRL9,0))return false;
        for(unsigned i=0;i<5;i++)if(i!=3 && !put(saved_regs[i],saved[i]))return false;
        if(!put(CTRL7,saved[3]))return false;
        changed=false;saved_valid=false;observing=false;
    }
    if(enrolled) {
        int32_t rc=gpio->wake_source(gpio->context,irq,true,0);
        if(rc==RISC_LIGHT_SLEEP_RETAINED){retained=true;return false;}
        if(rc!=0)return false;
        enrolled=false;
    }
    return true;
}
static bool configure_tap(bool wake) {
    if(!started || changed || enrolled || retained)return false;
    if(wake && (!irq || !gpio || gpio->struct_size<RISC_GPIO_BANK_WAKE_SOURCE_V1_SIZE || !gpio->wake_source))return false;
    for(unsigned i=0;i<5;i++)if(!read_regs(saved_regs[i],&saved[i],1))return false;
    saved_valid=true;changed=true;error=1;
    /* Asynchronous sample, interrupt data-ready disabled, accel only 500 Hz. */
    if(!put(CTRL7,0x20) || !put(CTRL1,0x40) || !put(CTRL8,0x80) ||
       !put(CTRL2,0x14) || !put(CTRL5,0))return false;
    /* Priority XYZ; 16-sample peak, 50-sample quiet, 250-sample double window. */
    const uint8_t windows[]={16,0,50,0,250,0,0,1};
    if(!write_regs(0x0b,windows,8) || !command(0x0c))return false;
    /* alpha=0.0625, gamma=0.25, peak encoded in 0.001 g^2 units, quiet 0.4 g^2. */
    const uint8_t levels[]={8,32,(uint8_t)threshold,(uint8_t)(threshold>>8),0x90,1,0,2};
    if(!write_regs(0x0b,levels,8) || !command(0x0c))return false;
    uint8_t stale;
    if(!read_regs(STATUS1,&stale,1) || !read_regs(TAP_STATUS,&stale,1) ||
       !put(CTRL8,0xc1) || !put(CTRL1,wake?0x48:0x40) || !put(CTRL7,0x21))return false;
    if(wake) {
        int32_t rc=gpio->wake_source(gpio->context,irq,true,RISC_WAKE_SET_LIGHT|RISC_WAKE_SET_DEEP);
        if(rc==RISC_LIGHT_SLEEP_RETAINED){retained=true;return false;}
        if(rc!=0)return false;
        enrolled=true;
    } else observing=true;
    error=0;return true;
}
static bool prepare_wake(void *context){(void)context;return configure_tap(true);}
static bool wake_pending(void *context,bool *out) {
    (void)context;if(!started || !out || !enrolled || retained)return false;
    /* STATUS1/TAP_STATUS acknowledge events. Use the physical level instead. */
    return gpio->read(gpio->context,irq,out);
}
static uint32_t wake_error(void *context){(void)context;return error;}
static bool observe_begin(void *context,uint16_t value) {
    return tap_configure(context,value) && configure_tap(false);
}
static bool observe(void *context,twatch_tap_observation_v1 *out) {
    (void)context;if(!out || !started || !observing || retained)return false;
    uint8_t status[2],tap=0;
    if(!read_regs(STATUS0,status,2))return false;
    if((status[1]&2u) && !read_regs(TAP_STATUS,&tap,1))return false;
    twatch_tap_observation_v1 value={.struct_size=sizeof(value),.double_tap=(tap&3u)==2u};
    if(status[0]&1u) {
        twatch_accel_sample_v1 accel;
        if(!sample(NULL,&accel))return false;
        value.sample_ready=true;value.x_mg=accel.x;value.y_mg=accel.y;value.z_mg=accel.z;
    }
    *out=value;return true;
}
static bool quiesce(void) {
    if(retained || !restore(NULL))return false;
    if(claim) {
        if(started && (!put(CTRL7,0) || !put(CTRL8,0x80)))return false;
        if(!bus->release_device(bus->context,claim))return false;
        claim=0;
    }
    if(irq){if(!gpio->release(gpio->context,irq))return false;irq=0;}
    started=false;return true;
}
static bool start(const risc_provider_dependency_v1 *deps,size_t n) {
    if(started || claim || irq || retained)return false;
    config=tw_config(deps,n,"qst,qmi8658c","peripheral.i2c",sizeof(*config));
    if(!tw_i2c_config_valid(config) || config->chip_id!=5 || !config->irq_active_high || config->irq_pull_up)return false;
    bus=tw_dep(deps,n,"i2c.bus",sizeof(*bus));gpio=tw_dep(deps,n,"gpio.bank",offsetof(risc_gpio_bank_api_v1,light_sleep));
    clock_api=tw_dep(deps,n,"platform.clock",sizeof(*clock_api));
    if(!tw_i2c_valid(bus) || !tw_gpio_valid(gpio) || !tw_clock_valid(clock_api))return false;
    if(!bus->claim_device(bus->context,config->address,&claim) ||
       (config->irq>=0&&!gpio->claim(gpio->context,config->irq,RISC_GPIO_INPUT,&irq)))goto failed;
    uint8_t id;
    if(!read_regs(WHOAMI,&id,1) || id!=5)goto failed;
    /* Mark all attempted state changes for cleanup, including failed writes. */
    started=true;
    if(!put(CTRL7,0) || !put(CTRL1,0x40) || !put(CTRL8,0x80) ||
       !put(CTRL2,0x16) || !put(CTRL5,0) || !put(CTRL7,0x21))goto failed;
    threshold=800;error=0;return true;
failed:
    (void)quiesce();return false;
}
static const twatch_motion_api_v1 api={1,sizeof(api),NULL,sample,chip_id,prepare_wake,wake_pending,
    restore,wake_error,tap_info,tap_configure,observe_begin,observe};
TW_DRIVER("qmi8658-motion","motion.accel",1,api)
