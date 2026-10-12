/* CO5300 command protocol from Waveshare's ESP32-S3-Touch-AMOLED-2.06
 * Arduino reference b099739. Controller commands stay in this ELF; the Runtime
 * exposes only owned one/four-lane SPI transactions. */
#include "DriverSupport.h"
#include "RiscSpiQuadV1.h"
#include "RiscDisplaySpiV2.h"
#include "twatch_power.h"
#include "common/gpio.h"
#define TWATCH_PANEL_POWER 1
#define WIDTH 410u
#define HEIGHT 502u
#define STRIDE (WIDTH*2u)
#define FORMAT RISC_DISPLAY_FORMAT_RGB565
#define DISPLAY_FLAGS (RISC_DISPLAY_INFO_ASYNC_PRESENT|RISC_DISPLAY_INFO_BRIGHTNESS)
#define DISPLAY_ID "waveshare-panel"
static const risc_hw_spi_display_v1 *config;
static const risc_spi_quad_v1 *quad;
static const garden_spi_v1 *spi;
static uint64_t spi_claim;
static bool spi_held,asleep,sleep_prepared,unblank_pending,deep_held,deep_retained;
static uint32_t spi_timeout_ms=20;
static uint8_t brightness=102;
static uint64_t row_deadline;
static bool end_bus(void) {
    if(!spi_held)return true;
    if(!spi->end(spi->context,spi_claim))return false;
    spi_held=false;return true;
}
static bool begin_bus(void) {
    if(spi_held)return false;
    uint32_t timeout=spi_timeout_ms;
    if(row_deadline){uint64_t now=timer->monotonic_ms(timer->context);if(now>=row_deadline)return false;timeout=(uint32_t)(row_deadline-now);}
    spi_held=true;
    if(spi->begin(spi->context,spi_claim,config->bus.frequency_hz,0,timeout))return true;
    (void)end_bus();return false;
}
static bool command(uint8_t cmd,const uint8_t *data,size_t n) {
    if(!begin_bus())return false;
    const uint8_t header[]={0x02,0,cmd,0};
    bool ok=spi->exchange(spi->context,spi_claim,header,NULL,sizeof(header));
    if(ok && n)ok=spi->exchange(spi->context,spi_claim,data,NULL,n);
    bool ended=end_bus();return ok&&ended;
}
static bool set_byte(uint8_t cmd,uint8_t value){return command(cmd,&value,1);}
static bool hw_start(const risc_provider_dependency_v1 *d,size_t n) {
    if(spi_claim||!gpio_clean())return false;
    const risc_hw_spi_display_v2 *c=tw_config_version(d,n,"chipone,co5300","display.spi",sizeof(*c),2);
    if(!c)return false;config=&c->base;
    if(config->width!=WIDTH||config->height!=HEIGHT||config->offset_x!=22||config->offset_y||
       config->rotation||config->reset_active_high||config->dc!=-1||config->backlight!=-1||config->busy!=-1||config->power_count||
       config->reserved[0]||config->reserved[1]||config->reserved[2]||!tw_pin(config->reset)||
       !tw_bus_limit(&config->bus,RISC_HW_BUS_SPI,80000000))return false;
    const int16_t selected[]={config->bus.sclk,config->bus.mosi,config->bus.miso,c->data2,c->data3,config->cs,config->reset};
    if(!tw_unique(selected,7)||!tw_pin(config->bus.miso)||!tw_pin(c->data2)||!tw_pin(c->data3)||!tw_pin(config->cs)||!gpio_dependencies(d,n))return false;
    quad=garden_dependency(d,n,"spi.bus",sizeof(*quad));
    if(!quad||quad->quad_tag!=RISC_SPI_QUAD_TAG||quad->quad_version!=RISC_SPI_QUAD_VERSION||!quad->claim_quad||!quad->exchange_quad)return false;
    spi=&quad->base;if(!spi->begin||!spi->exchange||!spi->end||!spi->release)return false;
    if(!gpio_claim(config->reset,true,true))return false;
    if(!quad->claim_quad(spi->context,config->bus.sclk,config->bus.mosi,config->bus.miso,c->data2,c->data3,config->cs,&spi_claim)||!spi_claim)return false;
    row_deadline=0;spi_timeout_ms=20;
    timer->sleep_ms(timer->context,10);gpio_write(config->reset,false);timer->sleep_ms(timer->context,200);
    gpio_write(config->reset,true);timer->sleep_ms(timer->context,200);if(io_fault)return false;
    if(!command(0x11,NULL,0))return false;timer->sleep_ms(timer->context,120);
    if(!set_byte(0xfe,0)||!set_byte(0xc4,0x80)||!set_byte(0x3a,0x55)||!set_byte(0x53,0x20)||
       !set_byte(0x63,0xff)||!set_byte(0x51,0)||!command(0x29,NULL,0)||!set_byte(0x58,0))return false;
    timer->sleep_ms(timer->context,10);
    asleep=sleep_prepared=false;unblank_pending=true;brightness=102;return true;
}
static void hw_submit(void) {}
static uint32_t hw_row_min_budget_ms(void) {return 1;}
static bool hw_row(uint32_t y,const uint8_t *pixels) {
    if(y>=HEIGHT)return false;
    row_deadline=timer->monotonic_ms(timer->context)+spi_timeout_ms;
    const uint16_t first=config->offset_x,last=first+WIDTH-1;
    const uint8_t columns[]={first>>8,first,last>>8,last};
    const uint8_t rows[]={y>>8,y,y>>8,y};
    bool ok=command(0x2a,columns,4)&&command(0x2b,rows,4)&&begin_bus();
    if(ok){const uint8_t header[]={0x32,0,0x2c,0};ok=spi->exchange(spi->context,spi_claim,header,NULL,sizeof(header));}
    uint8_t wire[512];
    for(size_t offset=0;ok&&offset<STRIDE;offset+=sizeof(wire)) {
        size_t count=STRIDE-offset;if(count>sizeof(wire))count=sizeof(wire);
        for(size_t i=0;i<count;i+=2){wire[i]=pixels[offset+i+1];wire[i+1]=pixels[offset+i];}
        ok=quad->exchange_quad(spi->context,spi_claim,wire,count);
    }
    bool ended=end_bus();row_deadline=0;return ok&&ended;
}
static int hw_finish(void) {
    if(unblank_pending){spi_timeout_ms=2;if(!set_byte(0x51,brightness))return -1;unblank_pending=false;}
    return 1;
}
static bool hw_brightness(uint16_t v,uint16_t maximum) {
    if(asleep||!maximum||v>maximum)return false;
    uint8_t requested=((uint32_t)v*255u+maximum/2u)/maximum;
    spi_timeout_ms=8;
    if(!unblank_pending&&!set_byte(0x51,requested))return false;
    brightness=requested;return true;
}
static bool hw_stop(void) {
    if(deep_held||deep_retained)return false;
    if(!end_bus())return false;
    if(spi_claim&&!spi->release(spi->context,spi_claim))return false;
    spi_claim=0;
    for(unsigned i=0;i<49;i++)gpio_release(i);
    return gpio_clean();
}
#include "common/display.h"
static bool panel_prepare_sleep(void *context) {
    (void)context;if(!enter())return false;
    bool ok=running&&!held&&!active&&!failed&&!deep_retained;
    if(ok&&asleep)ok=sleep_prepared;
    else if(ok){closing=asleep=true;unblank_pending=true;spi_timeout_ms=20;
        ok=set_byte(0x51,0)&&command(0x28,NULL,0)&&command(0x10,NULL,0);
        if(ok){timer->sleep_ms(timer->context,120);sleep_prepared=true;}}
    leave();return ok;
}
static bool panel_resume(void *context) {
    (void)context;if(!enter())return false;
    bool ok=running&&!deep_retained;
    if(ok&&deep_held){int32_t rc=gpio->deep_sleep_hold(gpio->context,pins[config->reset],false);
        if(rc==RISC_DEEP_SLEEP_RETAINED)deep_retained=true;ok=rc==0;if(ok)deep_held=false;}
    if(ok&&asleep){sleep_prepared=false;spi_timeout_ms=20;ok=command(0x11,NULL,0);
        if(ok){timer->sleep_ms(timer->context,120);ok=set_byte(0x51,0)&&command(0x29,NULL,0);}
        if(ok){asleep=false;closing=false;unblank_pending=true;}}
    leave();return ok;
}
static int32_t panel_prepare_deep_sleep(void *context) {
    if(deep_retained)return RISC_DEEP_SLEEP_RETAINED;
    if(!gpio||gpio->struct_size<GARDEN_GPIO_DEEP_SLEEP_HOLD_V1_SIZE||!gpio->deep_sleep_hold)return RISC_DEEP_SLEEP_UNSUPPORTED;
    if(deep_held)return sleep_prepared?0:RISC_DEEP_SLEEP_PLATFORM;
    if(!panel_prepare_sleep(context))return RISC_DEEP_SLEEP_PLATFORM;
    if(!enter())return RISC_DEEP_SLEEP_BUSY;
    int32_t rc=gpio->deep_sleep_hold(gpio->context,pins[config->reset],true);
    if(rc==0)deep_held=true;else if(rc==RISC_DEEP_SLEEP_RETAINED)deep_retained=true;
    leave();return rc;
}
static int32_t panel_resume_status(void *context) {
    if(deep_retained)return RISC_DEEP_SLEEP_RETAINED;
    return panel_resume(context)?RISC_LIGHT_SLEEP_OK:deep_retained?RISC_LIGHT_SLEEP_RETAINED:RISC_LIGHT_SLEEP_PLATFORM;
}
