#define main power_fixture_main
#include "test_power.c"
#undef main
#include "PortableNavigation.h"
#include "RiscPowerKeyV1.h"
static const risc_power_key_api_v1 logical={1,sizeof(logical),NULL,key_events};
static bool get_key(const char*n,uint32_t v,uint64_t i,risc_runtime_capability_v1*g){assert(!strcmp(n,"input.power-key")&&v==1&&!i);g->api=&logical;g->slot=1;g->generation=1;return true;}
static bool drop_key(risc_runtime_capability_v1*g){assert(g->api==&logical);return true;}
static bool healthy(risc_runtime_health_v1*h){(void)h;return true;}
static bool diag(const char*s){(void)s;return true;}
static void yield_ms(uint32_t ms){tick_+=ms;}
int main(void){
 setup();assert(start(deps_,4));
 risc_runtime_api_v1 rt={.api_version=1,.struct_size=sizeof(rt),.acquire=get_key,.release=drop_key,.health=healthy,.diagnostic=diag,.yield_ms=yield_ms};
 const risc_input_navigation_api_v1 *navigation=portable_input_navigation_open(&rt);assert(navigation);
 assert(navigation->foreground(navigation->context,NULL,0));
 risc_input_navigation_frame_v1 frame;assert(navigation->poll(NULL,&frame)&&!frame.pressed);
 pin_levels_[TEST_KEY_PIN]=TEST_KEY_HIGH;tick_=100;power_poll(1);tick_=120;power_poll(1);
 pin_levels_[TEST_KEY_PIN]=!TEST_KEY_HIGH;tick_=180;power_poll(1);tick_=200;power_poll(1);
 tick_=500;assert(navigation->poll(NULL,&frame)&&frame.pressed==RISC_NAV_BACK&&frame.released==RISC_NAV_BACK);
 assert(navigation->poll(NULL,&frame)&&!frame.pressed);
 portable_input_navigation_close(&rt);assert(quiesce());no_claims_();
 puts("Actual GPIO provider -> input.power-key -> shared navigation: delayed short becomes one Back PASS");
}
