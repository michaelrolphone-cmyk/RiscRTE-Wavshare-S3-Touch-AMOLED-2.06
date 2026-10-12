/* Generic one-bit SD memory + FatFs volume. Pins belong to the selected board
 * descriptor in [CLK,CMD,DAT0,DAT3] order, not this implementation. DAT3 stays
 * high so native initialization does not select SPI mode. Never formats media. */
#include "DriverSupport.h"
#include "RiscGpioSdmmcV1.h"
#include "RiscProviderSyncV1.h"
#include "RiscStorageVolumeV1.h"
static const garden_gpio_v1 *gpio_api;
static const risc_sdmmc_host_api_v1 *host;
static const risc_provider_sync_api_v1 *guard;
static const risc_platform_clock_api_v1 *clock_api;
static const risc_hw_gpio_bank_v1 *config;
static uint64_t card_token,select_token,lock_token;
static uint64_t sector_count;
static bool started,mounted,card_ready,io_failed,poisoned,guard_held;
static char error[128];
static bool equal(const char *a,const char *b){return strcmp(a,b)==0;}
static bool fail(const char *s) {
    size_t n=strlen(s);if(n>=sizeof(error))n=sizeof(error)-1;
    memcpy(error,s,n);error[n]=0;return false;
}
static bool guard_enter(void) {
    if(poisoned||!guard||!lock_token||!guard->is_owner(guard->context))return false;
    if(!guard->try_lock(guard->context,lock_token))return false;
    guard_held=true;return true;
}
static bool guard_leave(void) {
    if(!guard_held||!guard->unlock(guard->context,lock_token)) {
        poisoned=true;return false;
    }
    guard_held=false;return true;
}
static void cooperate(uint32_t bytes){(void)bytes;/* Native copied I/O is synchronous and owner-bounded. */}
static bool transport_idle(void){return !poisoned;}
static bool release_card(void) {
    if(card_token&&!host->release(host->context,card_token))return fail("SD controller cleanup incomplete");
    card_token=0;sector_count=0;card_ready=false;return true;
}
static bool read_sector(uint32_t lba,uint8_t out[512]) {
    return card_ready&&!io_failed&&card_token&&lba<sector_count&&host->read(host->context,card_token,lba,1,out);
}
static bool write_sector(uint32_t lba,const uint8_t in[512]) {
    return card_ready&&!io_failed&&card_token&&lba<sector_count&&host->write(host->context,card_token,lba,1,in);
}
static bool sync_card(void){return card_ready&&!io_failed&&card_token&&host->sync(host->context,card_token);}
static bool mount_filesystem(void);
static bool init_card(void) {
    if(!release_card()){poisoned=true;return false;}
    risc_sdmmc_card_info_v1 info={.struct_size=sizeof(info)};
    if(!host->open(host->context,config->pins[0],config->pins[1],config->pins[2],
                   RISC_SDMMC_MAX_HZ,&card_token,&info)) {
        bool clean=release_card();if(!clean)poisoned=true;
        return fail(clean?"SD card unavailable; insert and refresh":"SD initialization cleanup incomplete");
    }
    if(!card_token||info.struct_size<sizeof(info)||info.sector_size!=512||!info.sector_count||
       info.sector_count>UINT32_MAX||!info.clock_hz||info.clock_hz>RISC_SDMMC_MAX_HZ) {
        if(!release_card())poisoned=true;
        return fail("SD card metadata invalid");
    }
    sector_count=info.sector_count;card_ready=true;
    return mount_filesystem();
}
#define STORAGE_VOLUME_EXTERNAL_GUARD
#define STORAGE_VOLUME_GUARD_ENTER guard_enter
#define STORAGE_VOLUME_GUARD_LEAVE guard_leave
#define STORAGE_VOLUME_LABEL "SD card"
#include "../../lib/storage_fatfs/volume.c"
static bool quiesce(void) {
    if(poisoned)return false;
    if(lock_token) {
        if(!guard_enter())return false;
        if(has_handles()){(void)guard_leave();return false;}
        if(f_mount(NULL,"",0)!=FR_OK){(void)guard_leave();return false;}
        mounted=false;
        const bool retired=release_card();
        const bool unlocked=guard_leave();
        if(!retired||!unlocked)return false;
    }
    if(card_token&&!release_card())return false;
    if(select_token) {
        if(!gpio_api->release(gpio_api->context,select_token))return false;
        select_token=0;
    }
    if(lock_token) {
        if(!guard->destroy(guard->context,lock_token))return false;
        lock_token=0;
    }
    started=mounted=card_ready=io_failed=power_down_prepared=false;
    return true;
}
static bool start(const risc_provider_dependency_v1 *deps,size_t n) {
    if(started||card_token||select_token||lock_token||poisoned)return false;
    config=tw_config(deps,n,"sd,sd-memory-1bit","gpio.bank",sizeof(*config));
    if(!config||config->count!=4||!config->pull_up||config->reserved||!config->active_high||
       config->debounce_us||config->long_press_us||config->click_min_us||!tw_unique(config->pins,4))return false;
    for(unsigned i=0;i<4;i++)if(!tw_pin(config->pins[i]))return false;
    gpio_api=tw_dep(deps,n,"platform.gpio",sizeof(*gpio_api));
    clock_api=tw_dep(deps,n,"platform.clock",sizeof(*clock_api));
    guard=tw_dep(deps,n,"platform.sync",sizeof(*guard));
    host=risc_gpio_sdmmc(gpio_api);
    if(!host||!gpio_api->claim||!gpio_api->write||!gpio_api->release||!tw_clock_valid(clock_api)||
       !guard||!guard->is_owner||!guard->create||!guard->try_lock||!guard->unlock||!guard->destroy)return false;
    if(!guard->is_owner(guard->context)||!guard->create(guard->context,&lock_token)||!lock_token)return false;
    if(!gpio_api->claim(gpio_api->context,config->pins[3],true,true,false,&select_token)||!select_token) {
        (void)quiesce();return false;
    }
    error[0]=0;started=true;
    /* An empty/unformatted card is an available volume provider with no ready
     * media, not a reason to prevent the watch from opening. */
    if(!refresh(NULL)||poisoned){(void)quiesce();return false;}
    return true;
}
static void stop(void){(void)quiesce();}
static const risc_driver_v2 descriptor={2,sizeof(descriptor),"sdmmc-fatfs","storage.volume",1,&api,start,stop,quiesce};
__attribute__((visibility("default"))) const risc_driver_v2 *t5_driver_get(uint32_t version){return version==2?&descriptor:NULL;}
