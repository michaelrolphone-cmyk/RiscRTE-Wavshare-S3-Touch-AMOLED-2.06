/* Native transport SDK shims mirror Runtime's transport regression. All serial
 * parsing/cancellation and CPU entry guards are the selected Runtime sources. */
#include "ports/esp32s3/NativeSerialFiles.h"
#include "ports/esp32s3/SleepDiagnostics.h"
#include "ports/esp32s3/NativePlatform.h"
#include "bootstrap/Runtime.h"
#define private public
#include "ports/esp32s3/CpuPort.h"
#undef private
#include "NativeUsbTest.h"
#include <driver/usb_serial_jtag.h>
#include <hal/usb_serial_jtag_ll.h>
#include <esp_sleep.h>
#include "home_native_sleep_bridge.h"
#include <cstdio>
#include <cstdlib>
#include <cstring>
using namespace NativeUsbTest;
namespace N=RiscCpu::NativeSerialFiles;
namespace {
bool owner(){return task==reinterpret_cast<void*>(1);}
bool safe(){return true;}
struct DeepEntered {};
RiscCpu::Port::Gpio *scope=nullptr;
uint64_t crown=0;
uint32_t wake=RISC_LIGHT_SLEEP_WAKE_TIMER,armedMs=0;
unsigned lightEntries=0,deepCalls=0,deepEntries=0,transportReads=0;
unsigned lightOrdinary=0,lightTimed=0,lightSet=0,deepOrdinary=0,deepTimed=0,deepSet=0;
}
extern "C" {
int64_t esp_timer_get_time(){return now;}
uint32_t esp_get_free_heap_size(){return 100000;}
int esp_reset_reason(){return ESP_RST_POWERON;}
int esp_sleep_get_wakeup_cause(){return 0;}
void vTaskDelay(TickType_t ticks){now+=int64_t(ticks)*10000;}
BaseType_t xPortGetCoreID(){return core;}
TaskHandle_t xTaskGetCurrentTaskHandle(){return task;}
bool xPortInIsrContext(){return false;}
esp_err_t usb_serial_jtag_driver_install(usb_serial_jtag_driver_config_t *config){
    assert(!installed&&config&&config->rx_buffer_size==256&&config->tx_buffer_size>=256);
    ++installs;usb_serial_jtag_ll_phy_enable_external(false);usb_serial_jtag_ll_phy_enable_pad(true);
    installed=true;installedCore=core;return ESP_OK;
}
esp_err_t usb_serial_jtag_driver_uninstall(){assert(installed&&installedCore==core);++uninstalls;installed=false;return ESP_OK;}
bool usb_serial_jtag_is_driver_installed(){return installed;}
bool usb_serial_jtag_is_connected(){return host;}
int usb_serial_jtag_read_bytes(void *,uint32_t length,uint32_t ticks){assert(installed&&length==1&&!ticks);++transportReads;return 0;}
int usb_serial_jtag_write_bytes(const void *,size_t length,uint32_t ticks){assert(installed&&length<=64&&!ticks);++writes;return 0;}
int32_t wave_native_light(uint32_t ms,bool wake_set,risc_light_sleep_result_v1 *out){
    assert(scope&&crown);
    if(wake_set){++lightSet;return RiscCpu::Port::gpioLightSleepSet(scope,crown,false,ms,out);}
    if(ms){++lightTimed;return RiscCpu::Port::gpioLightSleepFor(scope,crown,false,ms,out);}
    ++lightOrdinary;return RiscCpu::Port::gpioLightSleep(scope,crown,false,out);
}
int32_t wave_native_deep(uint32_t ms,bool wake_set){
    assert(scope&&crown);++deepCalls;
    if(wake_set){++deepSet;return RiscCpu::Port::gpioDeepSleepSet(scope,crown,false,ms);}
    if(ms){++deepTimed;return RiscCpu::Port::gpioDeepSleepFor(scope,crown,false,ms);}
    ++deepOrdinary;return RiscCpu::Port::gpioDeepSleep(scope,crown,false);
}
}
int main(int argc,char **argv){
    assert(argc==3);
    const unsigned scenario=unsigned(std::strtoul(argv[1],nullptr,10));assert(scenario<WAVE_HOME_CASE_COUNT);
    const bool fixed=!std::strcmp(argv[2],"fixed");assert(fixed||!std::strcmp(argv[2],"baseline"));
    const bool deepExpected=scenario<=WAVE_HYBRID_SET_TIMED;
    const bool setExpected=scenario==WAVE_HYBRID_SET||scenario==WAVE_HYBRID_SET_TIMED;
    const bool timedDeep=scenario==WAVE_HYBRID_TIMED||scenario==WAVE_HYBRID_SET_TIMED;
    wake=(scenario==WAVE_GPIO_WAKE||scenario==WAVE_LIGHT_UNTIMED)?RISC_LIGHT_SLEEP_WAKE_GPIO:RISC_LIGHT_SLEEP_WAKE_TIMER;
    RiscPlatform::console.begin(115200);RiscDiagnostics::start();host=false;
    // A constructed, admitted endpoint with zero namespaces and no session.
    // This exercises cancellation independently of inserted SD media or files.
    N::Admission admission{nullptr,0,[](){return true;}};
    assert(N::prepare(&admission,owner,safe)&&N::exitSafe()&&!N::pending());
    RiscCpu::Hardware h{};h.owner=owner;h.now=[]()->uint64_t{return uint64_t(now/1000);};
    h.gpioOpen=[](uint8_t pin,bool output,bool,bool){return pin==0&&!output;};
    h.gpioClose=[](uint8_t pin){return pin==0;};
    h.gpioRead=[](uint8_t pin,bool *level){assert(pin==0);*level=true;return true;};
    h.usbPhyIdle=RiscDiagnostics::usbPhyIdle;
    h.wakeValid=[](uint8_t pin){return pin==0;};h.wakeArm=[](uint8_t pin,bool high){return pin==0&&!high;};
    h.wakeClear=[](uint8_t pin){return pin==0;};
    h.timerArm=[](uint32_t ms){assert(ms);armedMs=ms;return true;};h.timerClear=[](){armedMs=0;return true;};
    h.lightSleep=[](uint32_t *cause){
        ++lightEntries;now+=int64_t(armedMs)*1000;
        // IDF wake-cause ordinals: timer=4, GPIO=7. Diagnostics records only.
        RiscDiagnostics::lightReturn(ESP_OK,wake==RISC_LIGHT_SLEEP_WAKE_TIMER?4u:7u);
        *cause=wake;return true;
    };
    h.deepReady=[](){return true;};h.deepWakeValid=[](uint8_t pin){return pin==0;};
    h.deepWakeArm=[](uint8_t pin,bool high,bool pullup){return pin==0&&!high&&pullup;};
    h.deepWakeClear=[](uint8_t pin,bool pullup){return pin==0&&pullup;};
    h.deepWakeSetValid=[](uint64_t mask,uint64_t high){return mask==1&&!high;};
    h.deepWakeSetArm=[](uint64_t mask,uint64_t high,uint64_t pulls){return mask==1&&!high&&pulls==1;};
    h.deepWakeSetClear=[](uint64_t mask,uint64_t high,uint64_t pulls){return mask==1&&!high&&pulls==1;};
    h.deepSleep=[](){++deepEntries;throw DeepEntered{};};
    RiscCpu::Port port(h);scope=&port.gpios_[0];scope->port=&port;scope->input=1;scope->pullup=1;
    assert(RiscCpu::Port::gpioClaim(scope,0,false,false,true,&crown));
    bool terminal=false;
    try{wave_home_run(scenario);}catch(const DeepEntered&){terminal=true;}
    const auto o=wave_home_observe();
    std::printf("Home native case=%u expected=%s host=%d namespaces=0 session=0 result=%d stage=%u detail=%d pending=%d exit_safe=%d terminal=%d light=%u deep_calls=%u deep_entries=%u plans=%u alarm_resumes=%u restores=%u\n",
        scenario,argv[2],host,o.result,o.stage,o.detail,N::pending(),N::exitSafe(),terminal,lightEntries,deepCalls,deepEntries,o.plans,o.alarm_resumes,o.restores);
    std::fflush(stdout);
    assert(lightEntries==1&&o.alarm_resumes==1&&!host&&!transportReads&&!writes);
    assert(N::custodySafe()&&RiscDiagnostics::usbPhyIdle());
    assert(N::exitSafe()==fixed&&N::pending()!=fixed);
    if(deepExpected){
        assert(o.stage==6&&o.plans==2&&o.deep_prepares==1&&deepCalls==1);
        assert(terminal==fixed&&deepEntries==unsigned(fixed));
        if(fixed)assert(o.restores==0);
        else assert(o.result==0&&o.detail==RISC_DEEP_SLEEP_BUSY&&o.restores==1);
        assert(deepSet==unsigned(setExpected));
        assert(deepTimed==unsigned(!setExpected&&timedDeep));
        assert(deepOrdinary==unsigned(!setExpected&&!timedDeep));
    }else{
        assert(!terminal&&!deepCalls&&!deepEntries&&o.result==1&&o.stage==5&&o.detail==0&&o.restores==1);
        assert(o.plans==(scenario==WAVE_ALARM_DUE?2u:1u)&&!o.deep_prepares);
    }
    assert(lightSet==unsigned(setExpected));
    assert(lightOrdinary==unsigned(scenario==WAVE_LIGHT_UNTIMED));
    assert(lightTimed==unsigned(!setExpected&&scenario!=WAVE_LIGHT_UNTIMED));
    if(!terminal){wave_home_finish();assert(RiscCpu::Port::gpioRelease(scope,crown));}
    // Cleanup is explicitly after observations, never between Light and Deep.
    assert(N::shutdown()&&N::exitSafe());RiscPlatform::console.end();
    return 0;
}
