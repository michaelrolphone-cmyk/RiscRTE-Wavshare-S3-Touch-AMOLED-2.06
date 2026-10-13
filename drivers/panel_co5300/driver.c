/* CO5300 command protocol from Waveshare's ESP32-S3-Touch-AMOLED-2.06
 * Arduino reference b099739. Controller commands stay in this ELF; the Runtime
 * exposes only owned one/four-lane SPI transactions. SPI completion is NOT
 * panel readback: this controller link currently remains write-only. */
#include "DriverSupport.h"
#include "RiscSpiQuadV1.h"
#include "RiscDisplaySpiV2.h"
#include "twatch_power.h"
#include "RiscPowerRailV1.h"
#include "ProviderLog.h"
#include "common/gpio.h"
#define TWATCH_PANEL_POWER 1
#define WIDTH 410u
#define HEIGHT 502u
#define STRIDE (WIDTH*2u)
#define FORMAT RISC_DISPLAY_FORMAT_RGB565
#define DISPLAY_FLAGS (RISC_DISPLAY_INFO_ASYNC_PRESENT|RISC_DISPLAY_INFO_BRIGHTNESS)
#define DISPLAY_ID "waveshare-panel"
#ifndef CO5300_BOOT_PROBE
#define CO5300_BOOT_PROBE 0
#endif
static const risc_hw_spi_display_v1 *config;
static const risc_spi_quad_v1 *quad;
static const garden_spi_v1 *spi;
static const risc_power_rail_api_v1 *rail;
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
    /* Keep header and register parameters in one hardware SPI transaction,
     * using the framed path corresponding to the successful vendor A/B test. */
    if(n>4 || (n&&!data) || !begin_bus())return false;
    const risc_spi_frame_v1 frame={sizeof(frame),0x02,8,24,(uint64_t)cmd<<8,0,1,0};
    bool ok=quad->exchange_frame(spi->context,spi_claim,&frame,data,n);
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
    if(!quad||quad->quad_tag!=RISC_SPI_QUAD_TAG||quad->quad_version!=RISC_SPI_QUAD_VERSION||!quad->claim_quad||!quad->exchange_frame)return false;
    spi=&quad->base;if(!spi->begin||!spi->end||!spi->release)return false;
    provider_log("PANEL_LINK transport=framed-spi header=hardware-command-address completion=polling");
    rail=tw_dep(d,n,RISC_POWER_RAIL_CAPABILITY,sizeof(*rail));
    if(!rail || !rail->get_info || !rail->set_enabled)return false;
    /* Hold reset before rail configuration, then verify actual pad readback.
     * Rail selection is a generic dependency, never a cast of board.battery. */
    if(!gpio_claim(config->reset,true,false))return false;
    if(gpio_read(config->reset) || io_fault) {
        provider_log("PANEL_RESET stage=assert expected=0 result=failed");return false;
    }
    provider_log("PANEL_RESET stage=assert expected=0 readback=0");
    if(!rail->set_enabled(rail->context,true))return false;
    risc_power_rail_info_v1 supply={.struct_size=sizeof(supply)};
    if(!rail->get_info(rail->context,&supply) || !supply.configuration_verified || !supply.enabled) {
        provider_log("PANEL_POWER result=failed operation=consumer-readback");return false;
    }
    provider_log("PANEL_POWER result=ready consumer=display");
    if(!quad->claim_quad(spi->context,config->bus.sclk,config->bus.mosi,config->bus.miso,c->data2,c->data3,config->cs,&spi_claim)||!spi_claim)return false;
    row_deadline=0;spi_timeout_ms=20;
    timer->sleep_ms(timer->context,10);gpio_write(config->reset,false);timer->sleep_ms(timer->context,200);
    gpio_write(config->reset,true);timer->sleep_ms(timer->context,200);
    if(!gpio_read(config->reset) || io_fault) {
        provider_log("PANEL_RESET stage=release expected=1 result=failed");return false;
    }
    provider_log("PANEL_RESET stage=release expected=1 readback=1");
    if(!command(0x11,NULL,0))return false;timer->sleep_ms(timer->context,120);
    if(!set_byte(0xfe,0)||!set_byte(0xc4,0x80)||!set_byte(0x3a,0x55)||!set_byte(0x53,0x20)||
       !set_byte(0x63,0xff)||!command(0x29,NULL,0)||!set_byte(0x51,0)||!set_byte(0x58,0))return false;
    timer->sleep_ms(timer->context,10);
    /* Arduino_CO5300::tftInit() finishes with inversion off; begin() then
     * selects MADCTL RGB/rotation zero. Do not depend on reset defaults. */
    if(!command(0x20,NULL,0)||!set_byte(0x36,0))return false;
#if CO5300_BOOT_PROBE
    /* Bounded command-only white pulse for the black-screen bring-up image.
     * ALLPON ignores GRAM: a visible pulse tests reset/control/illumination
     * independently of four-lane pixel writes. It is NOT a success check.
     * At 25% brightness for 750 ms, before Home is admitted to the surface. */
    if(!set_byte(0x51,64)||!command(0x23,NULL,0))return false;
    provider_log("PANEL_PROBE phase=all-on brightness=64 duration_ms=750 control=write-only");
    timer->sleep_ms(timer->context,750);
    if(!command(0x13,NULL,0)||!set_byte(0x51,0))return false;
    provider_log("PANEL_PROBE phase=normal-mode-restored control=write-only");
#endif
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
    /* Vendor writeAddrWindow() starts RAM write in its own 0x02/0x2c
     * transaction. Arduino_ESP32QSPI::writePixels() then streams 0x32/0x3c
     * (WRMC), not an unqualified 0x32/0x2c. CS stays asserted across both
     * data chunks, preserving the row cursor. */
    bool ok=command(0x2a,columns,4)&&command(0x2b,rows,4)&&command(0x2c,NULL,0)&&begin_bus();
    uint8_t wire[512];
    for(size_t offset=0;ok&&offset<STRIDE;offset+=sizeof(wire)) {
        size_t count=STRIDE-offset;if(count>sizeof(wire))count=sizeof(wire);
        for(size_t i=0;i<count;i+=2){wire[i]=pixels[offset+i+1];wire[i+1]=pixels[offset+i];}
        const risc_spi_frame_v1 frame={sizeof(frame),offset?0:0x32,offset?0:8,
            offset?0:24,offset?0:0x3c00,0,4,0};
        ok=quad->exchange_frame(spi->context,spi_claim,&frame,wire,count);
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
    if(!brightness && requested) {
        provider_log("PANEL_BRIGHTNESS transition=off-to-on transport=complete visibility=unverified");
    }
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
