/* Generic Home display facade backed by the device-build vendor stack. */
#include "DriverSupport.h"
#include "RiscDisplayBackendV1.h"
#include "RiscDisplaySpiV2.h"
#include "RiscPowerRailV1.h"
#include "ProviderLog.h"
#include "twatch_power.h"
#define TWATCH_PANEL_POWER 1
#define WIDTH 410u
#define HEIGHT 502u
#define STRIDE (WIDTH*2u)
#define FORMAT RISC_DISPLAY_FORMAT_RGB565
#define DISPLAY_FLAGS (RISC_DISPLAY_INFO_ASYNC_PRESENT|RISC_DISPLAY_INFO_BRIGHTNESS)
#define DISPLAY_ID "waveshare-panel"
static const risc_platform_clock_api_v1* timer;
static const risc_display_backend_v1* backend;
static uint64_t backend_token;
static uint32_t spi_timeout_ms;
static uint8_t brightness=80;
static bool suspended;
static bool hw_start(const risc_provider_dependency_v1* d,size_t n){
 if(backend_token || !tw_config_version(d,n,"chipone,co5300","display.spi",sizeof(risc_hw_spi_display_v2),2))return false;
 timer=tw_dep(d,n,"platform.clock",sizeof(*timer));
 backend=tw_dep(d,n,RISC_DISPLAY_BACKEND_CAPABILITY,sizeof(*backend));
 const risc_power_rail_api_v1* rail=tw_dep(d,n,RISC_POWER_RAIL_CAPABILITY,sizeof(*rail));
 if(!tw_clock_valid(timer) || !backend || !backend->open || !backend->row || !backend->brightness || !backend->close || !rail || !rail->get_info)return false;
 risc_power_rail_info_v1 info={.struct_size=sizeof(info)};
 // Successful A/B made no PMIC writes. Match that established baseline.
 if(!rail->get_info(rail->context,&info) || !info.configuration_verified || !info.enabled || info.configured_millivolts!=3300)return false;
 provider_log("PANEL_LINK transport=vendor-Arduino_ESP32QSPI controller=vendor-Arduino_CO5300 native-spi=unused");
 suspended=false;brightness=80;return backend->open(backend->context,&backend_token);
}
static void hw_submit(void){}
static uint32_t hw_row_min_budget_ms(void){return 1;}
static bool hw_row(uint32_t y,const uint8_t* pixels){return backend->row(backend->context,backend_token,y,(const uint16_t*)pixels,WIDTH);}
static int hw_finish(void){return 1;}
static bool hw_brightness(uint16_t value,uint16_t maximum){
 if(!maximum || value>maximum)return false;
 uint8_t scaled=((uint32_t)value*255u+maximum/2u)/maximum;
 if(!backend->brightness(backend->context,backend_token,scaled))return false;
 brightness=scaled;return true;
}
static bool hw_stop(void){
 if(!backend_token)return true;
 if(!backend->close(backend->context,backend_token))return false;
 backend_token=0;return true;
}
#include "common/display.h"
// Close the native transport before CPU sleep: its ownership token is a
// deliberate native sleep barrier. Retain the framebuffer for rollback/wake.
static bool panel_prepare_sleep(void* c){
 (void)c;if(!enter())return false;
 bool ok=running&&!failed&&!held&&!active&&(!closing||suspended);
 if(ok){closing=suspended=true;ok=hw_stop();}
 leave();return ok;
}
static bool panel_resume(void* c){
 (void)c;if(!enter())return false;
 bool ok=running&&!failed&&(!closing||suspended);
 if(ok&&suspended){
  // A failed close/open can retain ownership. Complete that cleanup first.
  ok=hw_stop();
  if(ok)ok=backend->open(backend->context,&backend_token);
  if(ok)ok=backend->brightness(backend->context,backend_token,0);
  for(uint32_t y=0;ok&&y<HEIGHT;++y)ok=hw_row(y,pixels+y*STRIDE);
  if(ok)ok=backend->brightness(backend->context,backend_token,brightness);
  if(ok){suspended=false;closing=false;}
  else (void)hw_stop();
 }
 leave();return ok;
}
// Deep sleep additionally needs a qualified reset-pad hold contract.
static int32_t panel_prepare_deep_sleep(void* c){(void)c;return RISC_DEEP_SLEEP_UNSUPPORTED;}
static int32_t panel_resume_status(void* c){return panel_resume(c)?RISC_LIGHT_SLEEP_OK:RISC_LIGHT_SLEEP_PLATFORM;}
