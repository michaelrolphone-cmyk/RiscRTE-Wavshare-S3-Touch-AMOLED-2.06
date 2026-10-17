/* Generic one-bit SD memory + FatFs volume. Pins belong to the selected board
 * descriptor in [CLK,CMD,DAT0,DAT3] order, not this implementation. DAT3 stays
 * high so native initialization does not select SPI mode. Never formats media. */
#include "DriverSupport.h"
#ifndef WAVE_SD_ASYNC
#define WAVE_SD_ASYNC 0
#endif
#if WAVE_SD_ASYNC
#include <RiscStorageAsyncAdapterV1.h>
static const risc_storage_worker_v1 *storage_worker;
static risc_storage_async_adapter_v1 async_adapter;
static bool worker_guard,worker_scope_claimed;
static risc_platform_clock_api_v1 worker_clock;
static risc_storage_volume_api_v1_native_capacity capacity_api;
#define admission_api capacity_api.base
#define download_api admission_api.base
#define package_api download_api.base
#define asynchronous_api package_api.base
#define filesystem_api asynchronous_api.fs
#define state_api filesystem_api.state
#define STORAGE_VOLUME_NATIVE_CAPACITY
#endif
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
#if WAVE_SD_ASYNC
#include <RiscStorageExportV1.h>
enum {EXPORT_LOCAL,EXPORT_PREPARING,EXPORT_HOST,EXPORT_RETAINED};
static unsigned export_state;
static uint64_t export_token,export_generation;
#define STORAGE_VOLUME_ADMISSION_FROZEN() (export_state!=EXPORT_LOCAL)
#endif
static char error[128];
static bool equal(const char *a,const char *b){return strcmp(a,b)==0;}
static bool fail(const char *s) {
    size_t n=strlen(s);if(n>=sizeof(error))n=sizeof(error)-1;
    memcpy(error,s,n);error[n]=0;return false;
}
static bool guard_enter(void) {
#if WAVE_SD_ASYNC
    if(storage_worker && storage_worker->io->on_worker(storage_worker->io->context)){
        if(worker_guard||poisoned)return false;
        worker_guard=true;return true;
    }
    if(async_adapter.session)return false;
#endif
    if(poisoned||!guard||!lock_token||!guard->is_owner(guard->context))return false;
    if(!guard->try_lock(guard->context,lock_token))return false;
    guard_held=true;return true;
}
static bool guard_leave(void) {
#if WAVE_SD_ASYNC
    if(storage_worker && storage_worker->io->on_worker(storage_worker->io->context)){
        if(!worker_guard)return false;
        worker_guard=false;return !poisoned;
    }
#endif
    if(!guard_held||!guard->unlock(guard->context,lock_token)) {
        poisoned=true;return false;
    }
    guard_held=false;return true;
}
static void cooperate(uint32_t bytes){(void)bytes;/* Native copied I/O is synchronous and owner-bounded. */}
static bool transport_idle(void){return !poisoned;}
static bool release_card(void) {
    if(card_token&&!
#if WAVE_SD_ASYNC
       storage_worker->io->close(storage_worker->io->context)
#else
       host->release(host->context,card_token)
#endif
       )return fail("SD controller cleanup incomplete");
    card_token=0;sector_count=0;card_ready=false;return true;
}
static bool read_sector(uint32_t lba,uint8_t out[512]) {
    return card_ready&&!io_failed&&card_token&&lba<sector_count&&
#if WAVE_SD_ASYNC
    storage_worker->io->read(storage_worker->io->context,lba,1,out)
#else
    host->read(host->context,card_token,lba,1,out)
#endif
;
}
static bool write_sector(uint32_t lba,const uint8_t in[512]) {
    return card_ready&&!io_failed&&card_token&&lba<sector_count&&
#if WAVE_SD_ASYNC
    storage_worker->io->write(storage_worker->io->context,lba,1,in)
#else
    host->write(host->context,card_token,lba,1,in)
#endif
;
}
static bool sync_card(void){return card_ready&&!io_failed&&card_token&&
#if WAVE_SD_ASYNC
    storage_worker->io->sync(storage_worker->io->context)
#else
    host->sync(host->context,card_token)
#endif
;}
static bool mount_filesystem(void);
static bool init_card(void) {
    if(!release_card()){poisoned=true;return false;}
    risc_sdmmc_card_info_v1 info={.struct_size=sizeof(info)};
    #if WAVE_SD_ASYNC
    // DAT3 is a mode-select line, not a switched power rail. Never pulse it.
    bool opened=storage_worker->io->open(storage_worker->io->context,&info);
    card_token=1; // Failed open may retain native custody; close it explicitly.
    if(!opened) {
#else
    if(!host->open(host->context,config->pins[0],config->pins[1],config->pins[2],
                   RISC_SDMMC_MAX_HZ,&card_token,&info)) {
#endif
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
/* Reuse the checked zero-handle sleep transaction. The provider, not the CPU
 * readiness predicate, owns FAT unmount, transport close and reversible mount.
 * DAT3 is a static mode-select output and remains high throughout sleep. */
static bool sleep_transport_commit(void);
static bool sleep_transport_resume(void);
#define STORAGE_VOLUME_TRY_COMMIT_POWER_DOWN() sleep_transport_commit()
#define STORAGE_VOLUME_TRY_RESUME_POWER_DOWN() sleep_transport_resume()
#if WAVE_SD_ASYNC
#define STORAGE_VOLUME_SLEEP_UNSAFE() (poisoned || async_adapter.retained || export_state == EXPORT_RETAINED)
#else
#define STORAGE_VOLUME_SLEEP_UNSAFE() (poisoned)
#endif
#include "../../lib/storage_fatfs/volume.c"
static bool sleep_transport_commit(void) {
    /* commit_sleep already unmounted. The legacy terminal prefix may still
     * have a mounted filesystem; it cannot resume after committing. */
    if(mounted && f_mount(NULL,"",0)!=FR_OK){poisoned=true;return false;}
    mounted=false;
    if(!release_card()){poisoned=true;return false;}
    return true;
}
static bool sleep_transport_resume(void) {
    /* A missing/unformatted card is clean unavailability, never permission to
     * format it. Failed close or I/O remains retained through the shared ABI. */
    (void)init_card();
    return !poisoned;
}
#if WAVE_SD_ASYNC
#include "Export.h"
#include "Async.h"
#endif
static bool quiesce(void) {
    if(poisoned || sleep_state==SLEEP_RETAINED)return false;
#if WAVE_SD_ASYNC
    if(export_state!=EXPORT_LOCAL||async_adapter.session||async_adapter.operation||async_adapter.retained)return false;
#endif
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
    #if WAVE_SD_ASYNC
    if(worker_scope_claimed){
        if(storage_worker->unbind(storage_worker->context)!=RISC_STORAGE_WORK_OK||storage_worker->release(storage_worker->context)!=RISC_STORAGE_WORK_OK)return false;
        worker_scope_claimed=false;
    }
#endif
    if(select_token) {
        if(!gpio_api->release(gpio_api->context,select_token))return false;
        select_token=0;
    }
    if(lock_token) {
        if(!guard->destroy(guard->context,lock_token))return false;
        lock_token=0;
    }
    started=mounted=card_ready=io_failed=power_down_prepared=power_down_committed=false;
    sleep_state=SLEEP_ACTIVE;
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
    #if WAVE_SD_ASYNC
    storage_worker=tw_dep(deps,n,RISC_STORAGE_WORKER_CAPABILITY,sizeof(*storage_worker));
    if(!storage_worker||!storage_worker->io||!storage_worker->claim||!storage_worker->bind||!storage_worker->submit||!storage_worker->collect||!storage_worker->cancel||!storage_worker->unbind||!storage_worker->release)return false;
    const risc_storage_work_io_v1 *io=storage_worker->io;
    if(!io->on_worker||!io->now_ms||!io->delay_ms||!io->open||!io->read||!io->write||!io->sync||!io->close)return false;
#endif
    if(!guard->is_owner(guard->context)||!guard->create(guard->context,&lock_token)||!lock_token)return false;
#if WAVE_SD_ASYNC
    const risc_storage_work_scope_v1 scope={config->pins[3],config->pins[0],config->pins[1],config->pins[2],RISC_SDMMC_MAX_HZ,true};
    if(storage_worker->claim(storage_worker->context,&scope)!=RISC_STORAGE_WORK_OK)return false;
    worker_scope_claimed=true;
    async_adapter.worker=storage_worker;async_adapter.volume=&api.terminal.power.volume.base;async_adapter.ext=&api.terminal.power.volume;async_adapter.fs=&filesystem_api;async_adapter.native_capacity=fs_native_capacity;
    if(storage_worker->bind(storage_worker->context,risc_storage_async_execute,&async_adapter)!=RISC_STORAGE_WORK_OK)return false;
    worker_clock=(risc_platform_clock_api_v1){1,sizeof(worker_clock),NULL,worker_now,worker_delay};clock_api=&worker_clock;
#else
    if(!gpio_api->claim(gpio_api->context,config->pins[3],true,true,false,&select_token)||!select_token) {
        (void)quiesce();return false;
    }
    #endif
    error[0]=0;started=true;
#if WAVE_SD_ASYNC
    return true; // First copied REFRESH owns card I/O; no mount on graph activation.
#endif
    /* An empty/unformatted card is an available volume provider with no ready
     * media, not a reason to prevent the watch from opening. */
    if(!refresh(NULL)||poisoned){(void)quiesce();return false;}
    return true;
}
static void stop(void){(void)quiesce();}
static const risc_driver_v2 descriptor={2,sizeof(descriptor),"sdmmc-fatfs","storage.volume",1,
#if WAVE_SD_ASYNC
 &capacity_api,
#else
 &api,
#endif
 start,stop,quiesce};
__attribute__((visibility("default"))) const risc_driver_v2 *t5_driver_get(uint32_t version){
#if WAVE_SD_ASYNC
 if(version==2)publish_async();
#endif
 return version==2?&descriptor:NULL;}
