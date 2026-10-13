#pragma once
/* Diagnostic adapter only: the unmodified production native SPI implementation
 * supplies all transactions. The vendor CO5300 controller class supplies panel
 * initialization and drawing, as it does in the reference phases. This is not
 * a replacement public capability or a board-specific change to shared Home. */
#include <Arduino_DataBus.h>
#include <driver/spi_master.h>
#include <driver/gpio.h>
#include <esp_rom_gpio.h>
#include <esp_timer.h>
#include <soc/gpio_sig_map.h>
#include <cstring>
namespace LinkNative {
static TickType_t ticks(uint32_t ms){return ms?pdMS_TO_TICKS(ms)+1:0;}
static spi_host_device_t host(uint8_t physical){return physical==2?SPI2_HOST:SPI3_HOST;}
static bool gpioWrite(uint8_t pin,bool level){return gpio_set_level(static_cast<gpio_num_t>(pin),level)==ESP_OK;}
static bool gpioClose(uint8_t pin){return gpio_reset_pin(static_cast<gpio_num_t>(pin))==ESP_OK;}
#include "ports/esp32s3/NativeSpi.inc"
}
class NativeBus final: public Arduino_DataBus {
 public:
  bool failed=false;unsigned transactions=0;
  bool begin(int32_t speed=40000000,int8_t mode=GFX_NOT_DEFINED) override {
    _speed=speed;_dataMode=mode==GFX_NOT_DEFINED?0:mode;
    pinMode(12,OUTPUT);digitalWrite(12,HIGH);
    return LinkNative::spiOpenQuad(2,11,4,5,6,7);
  }
  void beginWrite() override {}
  void endWrite() override {}
  void writeCommand(uint8_t c) override {reg(c,nullptr,0);}
  void writeCommand16(uint16_t) override {bad("unsupported-command16");}
  void writeCommandBytes(uint8_t*,uint32_t) override {bad("unsupported-command-bytes");}
  void writeC8D8(uint8_t c,uint8_t v) override {reg(c,&v,1);}
  void writeC8D16(uint8_t c,uint16_t v) override {uint8_t b[]={uint8_t(v>>8),uint8_t(v)};reg(c,b,2);}
  void writeC8D16D16(uint8_t c,uint16_t a,uint16_t b) override {
    uint8_t p[]={uint8_t(a>>8),uint8_t(a),uint8_t(b>>8),uint8_t(b)};reg(c,p,4);
  }
  void write(uint8_t v) override {writeBytes(&v,1);}
  void write16(uint16_t v) override {writePixels(&v,1);}
  void writeBytes(uint8_t* data,uint32_t n) override {
    if(!n||!beginPixels())return;
    for(uint32_t i=0;i<n&&!failed;i+=512)check(LinkNative::spiTransferQuad(2,data+i,(n-i)>512?512:n-i,8),"bytes");
    finish();
  }
  void writePixels(uint16_t* data,uint32_t n) override {pixels(data,0,n);}
  void writeRepeat(uint16_t v,uint32_t n) override {pixels(nullptr,v,n);}
 private:
  void bad(const char* stage){if(!failed)Serial.printf("LINK_TEST raw_error=%s\n",stage);failed=true;}
  bool check(bool ok,const char* stage){if(!ok)bad(stage);return ok;}
  bool start(){if(failed)return false;return check(LinkNative::spiBegin(2,12,_speed,_dataMode,1000),"begin");}
  void finish(){if(LinkNative::spi[0].held)check(LinkNative::spiEnd(2,12,8),"end");++transactions;}
  void reg(uint8_t c,const uint8_t* data,size_t n){
    if(n>4){bad("parameter-size");return;}
    uint8_t bytes[8]={2,0,c,0};if(n)memcpy(bytes+4,data,n);
    if(!start()){finish();return;}
    check(LinkNative::spiTransfer(2,bytes,nullptr,n+4,8),"register");finish();
  }
  bool beginPixels(){
    if(!start()){finish();return false;}
    const uint8_t prefix[]={0x32,0,0x3c,0};
    if(!check(LinkNative::spiTransfer(2,prefix,nullptr,4,8),"pixel-prefix")){finish();return false;}
    return true;
  }
  void pixels(const uint16_t* data,uint16_t repeated,uint32_t n){
    if(!n||!beginPixels())return;
    uint8_t wire[512];
    for(uint32_t i=0;i<n&&!failed;){unsigned count=(n-i)>256?256:n-i;
      for(unsigned x=0;x<count;x++){uint16_t p=data?data[i+x]:repeated;wire[x*2]=p>>8;wire[x*2+1]=p;}
      check(LinkNative::spiTransferQuad(2,wire,count*2,8),"pixels");i+=count;
    }
    finish();
  }
};
