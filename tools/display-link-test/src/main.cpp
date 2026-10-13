/* Deliberate standalone fault-isolation firmware, NOT shared Home.
 * The stock vendor panel/controller source is identical in all four phases.
 * Software resets give each SPI implementation an independent fresh lifetime.
 * PMIC is read only. No storage/filesystem/network/sleep services are used. */
#include <Arduino.h>
#include <Wire.h>
#include <esp_system.h>
#include <esp_attr.h>
#include <driver/gpio.h>
#include <soc/gpio_struct.h>
#include <soc/io_mux_reg.h>
#include <Arduino_GFX.h>
#include <databus/Arduino_ESP32QSPI.h>
#include <display/Arduino_CO5300.h>
#include "NativeBus.h"

RTC_NOINIT_ATTR static uint32_t next_phase;
RTC_NOINIT_ATTR static uint32_t phase_check;
static constexpr uint32_t MAGIC=0x574c5434;
static const char* labels[]={"A VENDOR 80 MHz","B VENDOR 40 MHz","C RAW 40 MHz","D RAW 5 MHz"};
static const uint32_t speeds[]={80000000,40000000,40000000,5000000};
static unsigned phase;
static Arduino_CO5300* display;
static NativeBus* native;
static uint32_t started,last_log;
static unsigned frames;
static bool ready;
static bool pmic_read(uint8_t reg,uint8_t& value){
  Wire.beginTransmission(0x34);Wire.write(reg);
  if(Wire.endTransmission(false)!=0)return false;
  if(Wire.requestFrom(uint8_t(0x34),uint8_t(1),true)!=1)return false;
  value=Wire.read();return true;
}
static void pads(){
  for(unsigned pin:{4u,5u,6u,7u,8u,11u,12u})
    Serial.printf("LINK_PAD pin=%u input=%d enable=%u mux=0x%08lx matrix=0x%08lx\n",pin,
      gpio_get_level(static_cast<gpio_num_t>(pin)),unsigned((GPIO.enable>>pin)&1u),
      (unsigned long)REG_READ(GPIO_PIN_MUX_REG[pin]),(unsigned long)GPIO.func_out_sel_cfg[pin].val);
}
void setup(){
  Serial.begin(115200);delay(1000);
  phase=(esp_reset_reason()==ESP_RST_SW&&next_phase<4&&phase_check==(MAGIC^next_phase))?next_phase:0;
  Serial.printf("\nLINK_TEST version=1 phase=%u label=\"%s\" hz=%lu reset=%d\n",phase,labels[phase],(unsigned long)speeds[phase],int(esp_reset_reason()));
  Serial.println("LINK_TEST vendor=b099739ad0e33b34e5fbaae77f02bd84805d79a3 native=8aae8df4f9139bea06ff43888ed628c45ed8a057");
  Wire.begin(15,14,400000);Wire.setTimeOut(30);
  uint8_t id=0,en=0,voltage=0;
  bool pmic=pmic_read(3,id)&&pmic_read(0x90,en)&&pmic_read(0x93,voltage);
  Serial.printf("LINK_TEST pmic_read=%u chip=0x%02x reg90=0x%02x reg93=0x%02x writes=none\n",pmic,id,en,voltage);
  Wire.end();
  Arduino_DataBus* bus;
  if(phase<2)bus=new Arduino_ESP32QSPI(12,11,4,5,6,7);
  else {native=new NativeBus;bus=native;}
  display=new Arduino_CO5300(bus,8,0,410,502,22,0,0,0);
  Serial.println("LINK_TEST panel_begin=starting");
  ready=display->begin(speeds[phase]);
  Serial.printf("LINK_TEST panel_begin=%s transport_only=1\n",ready?"ok":"failed");
  if(ready){display->setBrightness(80);display->fillScreen(0x0000);}
  pads();started=last_log=millis();
}
void loop(){
  unsigned age=millis()-started;
  if(ready&&(!native||!native->failed)&&age<12000){
    const uint16_t colors[]={0xf800,0x07e0,0x001f,0x7bef};
    display->fillScreen(colors[(age/3000)%4]);
    display->setTextColor(0xffff,0x0000);display->setTextSize(2);
    display->setCursor(30,100);display->println("DISPLAY LINK TEST");
    display->setCursor(30,135);display->println(labels[phase]);
    display->setCursor(30,175);display->printf("FRAME %u",++frames);
    display->setCursor(30,210);display->println("NO HOME IN THIS TEST");
    display->setCursor(30,250);display->println("Report visible phase");
  }
  if(millis()-last_log>=1000){last_log=millis();
    Serial.printf("LINK_TEST phase=%u seconds=%lu frames=%u raw_failed=%u raw_transactions=%u visibility=unverified\n",phase,(unsigned long)(age/1000),frames,native&&native->failed,native?native->transactions:0);
  }
  if(age>=12000){
    if(ready&&(!native||!native->failed)){display->setBrightness(0);display->displayOff();}
    next_phase=(phase+1)%4;phase_check=MAGIC^next_phase;
    Serial.printf("LINK_TEST phase=%u next=%lu deliberate_restart=1\n",phase,(unsigned long)next_phase);Serial.flush();delay(150);esp_restart();
  }
  delay(250);
}
