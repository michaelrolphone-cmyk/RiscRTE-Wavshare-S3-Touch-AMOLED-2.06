// Device-build extension. Vendor panel/transport implementation is pinned and
// instrumented for checked SPI calls and startup isolation; no NativeSpi calls.
#include "ports/esp32s3/CpuPort.h"
#include <Arduino_GFX.h>
#include <databus/Arduino_ESP32QSPI.h>
#include <display/Arduino_CO5300.h>
#include <driver/gpio.h>
#include <soc/gpio_struct.h>
#include <soc/io_mux_reg.h>
#include <soc/rtc_cntl_reg.h>
#include <soc/rtc_io_periph.h>
#include <Arduino.h>
#include <new>
namespace {
Arduino_ESP32QSPI* bus=nullptr;
Arduino_CO5300* panel=nullptr;
uint16_t width=0,height=0;int16_t reset=-1;
uint16_t paired[820];uint32_t pendingRow=UINT32_MAX;
bool accepts(const risc_hardware_device_v1& hw,uint8_t physical){
 if(physical!=2 || strcmp(hw.compatible,"chipone,co5300") || strcmp(hw.config_type,"display.spi") ||
    hw.config_version!=2 || hw.config_size!=sizeof(risc_hw_spi_display_v2) || !hw.config)return false;
 const auto& c=*static_cast<const risc_hw_spi_display_v2*>(hw.config);const auto& b=c.base;
 return b.width==410 && b.height==502 && b.offset_x==22 && !b.offset_y && !b.rotation &&
   !b.reset_active_high && b.reset>=0 && b.dc==-1 && b.backlight==-1 && b.busy==-1 && !b.power_count &&
   b.bus.frequency_hz==40000000 && !b.bus.mode && c.data2>=0 && c.data3>=0;
}
void pads(const char* stage){
 Serial.printf("PANEL_HOLD stage=%s pad=0x%08lx digital=0x%08lx iso=0x%08lx\n",stage,(unsigned long)REG_READ(RTC_CNTL_PAD_HOLD_REG),(unsigned long)REG_READ(RTC_CNTL_DIG_PAD_HOLD_REG),(unsigned long)REG_READ(RTC_CNTL_DIG_ISO_REG));
 for(unsigned pin:{4u,5u,6u,7u,8u,11u,12u})
  Serial.printf("PANEL_PAD stage=%s pin=%u input=%d enable=%u mux=0x%08lx matrix=0x%08lx out=%u rtc=0x%08lx\n",stage,pin,gpio_get_level(static_cast<gpio_num_t>(pin)),unsigned((GPIO.enable>>pin)&1u),(unsigned long)REG_READ(GPIO_PIN_MUX_REG[pin]),(unsigned long)GPIO.func_out_sel_cfg[pin].val,unsigned((GPIO.out>>pin)&1u),(unsigned long)(rtc_io_desc[rtc_io_num_map[pin]].reg?REG_READ(rtc_io_desc[rtc_io_num_map[pin]].reg):0));
}
bool closePanel(){
 // All vendor writes are synchronous. Keep objects and ownership on cleanup
 // refusal; caller retries without unloading its provider dependency.
 if(bus && !bus->riscClose())return false;
 delete panel;panel=nullptr;delete bus;bus=nullptr;
 if(reset>=0 && gpio_reset_pin(static_cast<gpio_num_t>(reset))!=ESP_OK)return false;
 reset=-1;width=height=0;return true;
}
bool openPanel(const risc_hardware_device_v1& hw,uint8_t physical){
 if(bus || panel || !accepts(hw,physical))return false;
 const auto& c=*static_cast<const risc_hw_spi_display_v2*>(hw.config);const auto& b=c.base;
 width=b.width;height=b.height;reset=b.reset;pendingRow=UINT32_MAX;
 pads("before-begin");
 bus=new(std::nothrow) Arduino_ESP32QSPI(b.cs,b.bus.sclk,b.bus.mosi,b.bus.miso,c.data2,c.data3);
 if(!bus)return false;
 panel=new(std::nothrow) Arduino_CO5300(bus,b.reset,b.rotation,b.width,b.height,b.offset_x,b.offset_y,0,0);
 if(!panel || !panel->begin(b.bus.frequency_hz))return false;
 // Same post-begin brightness as successful diagnostic A/B. Vendor begin
 // itself writes 0xD0 immediately after DISPON. No ALLPON/zero-brightness probe.
 panel->setBrightness(80);
 pads("after-begin");
 Serial.println("PANEL_PROBE phase=all-pixels-on before-dependent-providers=1");
 bus->sendCommand(0x23);delay(800);bus->sendCommand(0x22);
 Serial.println("PANEL_PROBE phase=red-fill before-dependent-providers=1");
 panel->fillScreen(0xf800);delay(1200);
 uint16_t scanline[410];for(auto& pixel:scanline)pixel=0x07e0;
 Serial.println("PANEL_PROBE phase=green-rows before-dependent-providers=1");
 for(unsigned y=0;y<height;++y){panel->startWrite();panel->writeAddrWindow(0,y,width,1);panel->writePixels(scanline,width);panel->endWrite();}
 delay(1200);
 Serial.println("PANEL_PROBE phase=blue-paired-rows before-dependent-providers=1");
 for(auto& pixel:paired)pixel=0x001f;
 for(unsigned y=0;y<height;y+=2){panel->startWrite();panel->writeAddrWindow(0,y,width,2);panel->writePixels(paired,width*2);panel->endWrite();}
 delay(1200);
 panel->fillScreen(0);
 return true;
}
bool row(uint32_t y,const uint16_t* pixels,size_t count){
 if(!panel || !pixels || count!=width || y>=height)return false;
 static bool first=true;if(first){first=false;pads("first-home-row");Serial.printf("PANEL_PIXELS first=%04x middle=%04x last=%04x\n",pixels[0],pixels[count/2],pixels[count-1]);}
 // The vendor LVGL rounder requires even starts and odd ends on both axes.
 // Retain one row; send only complete 410x2 windows with inclusive odd ends.
 if(!(y&1u)){if(pendingRow!=UINT32_MAX)return false;memcpy(paired,pixels,count*sizeof(uint16_t));pendingRow=y;return true;}
 if(pendingRow!=y-1)return false;
 memcpy(paired+width,pixels,count*sizeof(uint16_t));
 panel->startWrite();panel->writeAddrWindow(0,y-1,width,2);
 panel->writePixels(paired,width*2);panel->endWrite();pendingRow=UINT32_MAX;return true;
}
bool brightness(uint8_t value){if(!panel)return false;Serial.printf("PANEL_BRIGHTNESS value=%u\n",unsigned(value));pads("brightness");panel->setBrightness(value);return true;}
const RiscCpu::DisplayBackend backend={accepts,openPanel,row,brightness,closePanel};
}
namespace RiscCpu {const DisplayBackend* selectedDisplayBackend(){return &backend;}}
