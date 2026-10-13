// Device-build extension. Vendor panel/transport implementation is pinned and
// compiled unchanged except for an explicit cleanup method; no NativeSpi calls.
#include "ports/esp32s3/CpuPort.h"
#include <Arduino_GFX.h>
#include <databus/Arduino_ESP32QSPI.h>
#include <display/Arduino_CO5300.h>
#include <driver/gpio.h>
#include <new>
namespace {
Arduino_ESP32QSPI* bus=nullptr;
Arduino_CO5300* panel=nullptr;
uint16_t width=0,height=0;int16_t reset=-1;
bool accepts(const risc_hardware_device_v1& hw,uint8_t physical){
 if(physical!=2 || strcmp(hw.compatible,"chipone,co5300") || strcmp(hw.config_type,"display.spi") ||
    hw.config_version!=2 || hw.config_size!=sizeof(risc_hw_spi_display_v2) || !hw.config)return false;
 const auto& c=*static_cast<const risc_hw_spi_display_v2*>(hw.config);const auto& b=c.base;
 return b.width==410 && b.height==502 && b.offset_x==22 && !b.offset_y && !b.rotation &&
   !b.reset_active_high && b.reset>=0 && b.dc==-1 && b.backlight==-1 && b.busy==-1 && !b.power_count &&
   b.bus.frequency_hz==40000000 && !b.bus.mode && c.data2>=0 && c.data3>=0;
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
 width=b.width;height=b.height;reset=b.reset;
 bus=new(std::nothrow) Arduino_ESP32QSPI(b.cs,b.bus.sclk,b.bus.mosi,b.bus.miso,c.data2,c.data3);
 if(!bus)return false;
 panel=new(std::nothrow) Arduino_CO5300(bus,b.reset,b.rotation,b.width,b.height,b.offset_x,b.offset_y,0,0);
 if(!panel || !panel->begin(b.bus.frequency_hz))return false;
 // Same post-begin brightness as successful diagnostic A/B. Vendor begin
 // itself writes 0xD0 immediately after DISPON. No ALLPON/zero-brightness probe.
 panel->setBrightness(80);
 return true;
}
bool row(uint32_t y,const uint16_t* pixels,size_t count){
 if(!panel || !pixels || count!=width || y>=height)return false;
 panel->startWrite();panel->writeAddrWindow(0,y,width,1);
 panel->writePixels(const_cast<uint16_t*>(pixels),count);panel->endWrite();return true;
}
bool brightness(uint8_t value){if(!panel)return false;panel->setBrightness(value);return true;}
const RiscCpu::DisplayBackend backend={accepts,openPanel,row,brightness,closePanel};
}
namespace RiscCpu {const DisplayBackend* selectedDisplayBackend(){return &backend;}}
