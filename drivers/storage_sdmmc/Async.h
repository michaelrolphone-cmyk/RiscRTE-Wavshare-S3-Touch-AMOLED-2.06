/* Generic copied SD work, using the shared adapter and checked FatFs owner.
 * The mode-select DAT3 pin remains high throughout the claimed scope. */
static uint64_t worker_now(void*c){(void)c;return storage_worker->io->now_ms(storage_worker->io->context);}
static void worker_delay(void*c,uint32_t ms){(void)c;storage_worker->io->delay_ms(storage_worker->io->context,ms);}
static bool async_owner(void){return guard&&guard->is_owner(guard->context);}
static int32_t observe_state(void*c){
 (void)c;if(export_state==EXPORT_RETAINED)return RISC_STORAGE_STATE_RETAINED;
 if(export_state!=EXPORT_LOCAL||async_adapter.session)return RISC_STORAGE_STATE_UNAVAILABLE;
 if(poisoned||async_adapter.retained||sleep_state==SLEEP_RETAINED)return RISC_STORAGE_STATE_RETAINED;
 if(io_failed)for(unsigned i=0;i<FILE_SLOTS;++i)if(files[i].handle&&(files[i].flags&RISC_STORAGE_OPEN_WRITE))return RISC_STORAGE_STATE_RETAINED;
 return started&&mounted&&card_ready&&!io_failed&&!power_down_prepared?RISC_STORAGE_STATE_READY:RISC_STORAGE_STATE_UNAVAILABLE;
}
static int32_t async_begin_checked(void*c,uint64_t*t){
 (void)c;if(t)*t=0;
 // Exactly one owner check; no lock, filesystem call, cleanup or queue drain.
 if(!async_owner())return RISC_STORAGE_ASYNC_BUSY;
 if(!t)return RISC_STORAGE_ASYNC_INVALID;
 if(export_state==EXPORT_RETAINED)return RISC_STORAGE_ASYNC_RETAINED;
 if(export_state!=EXPORT_LOCAL||async_adapter.session)return RISC_STORAGE_ASYNC_BUSY;
 if(poisoned||async_adapter.retained||sleep_state==SLEEP_RETAINED)return RISC_STORAGE_ASYNC_RETAINED;
 if(!started||!lock_token||!worker_scope_claimed||guard_held||worker_guard||power_down_prepared||has_handles()||async_adapter.operation||async_adapter.file||async_adapter.directory||async_adapter.writing||async_adapter.written||async_adapter.ending||async_adapter.cleanup)return RISC_STORAGE_ASYNC_BUSY;
 return risc_storage_async_begin(&async_adapter,t);
}
static int32_t async_submit(void*c,uint64_t s,const risc_storage_async_request_v1*q,uint64_t*t){(void)c;return async_owner()?risc_storage_async_submit(&async_adapter,s,q,t):RISC_STORAGE_ASYNC_BUSY;}
static int32_t package_submit(void*c,uint64_t s,const risc_storage_package_request_v1*q,uint64_t*t){(void)c;return async_owner()?risc_storage_package_submit(&async_adapter,s,q,t):RISC_STORAGE_ASYNC_BUSY;}
static int32_t capacity_submit(void*c,uint64_t s,const risc_storage_native_capacity_request_v1*q,uint64_t*t){(void)c;return async_owner()?risc_storage_native_capacity_submit(&async_adapter,s,q,t):RISC_STORAGE_ASYNC_BUSY;}
static int32_t async_collect(void*c,uint64_t s,uint64_t t,risc_storage_async_result_v1*r){(void)c;return async_owner()?risc_storage_async_collect(&async_adapter,s,t,r):RISC_STORAGE_ASYNC_BUSY;}
static int32_t async_end(void*c,uint64_t s){(void)c;return async_owner()?risc_storage_async_end(&async_adapter,s):RISC_STORAGE_ASYNC_BUSY;}
static int32_t capacity_check(void*c,const risc_storage_native_capacity_result_v1*q){
 (void)c;if(!async_owner())return RISC_STORAGE_ASYNC_BUSY;
 if(!q||!q->serial||!q->mount_epoch)return RISC_STORAGE_ASYNC_INVALID;
 if(async_adapter.session||async_adapter.operation)return RISC_STORAGE_ASYNC_BUSY;
 if(poisoned||async_adapter.retained||sleep_state==SLEEP_RETAINED)return RISC_STORAGE_ASYNC_RETAINED;
 if(!mounted||!card_ready||io_failed||power_down_prepared||has_handles()||native_mount_epoch!=q->mount_epoch)return RISC_STORAGE_ASYNC_IO;
 return !memcmp(q,&async_adapter.capacity_receipt,sizeof(*q))?RISC_STORAGE_ASYNC_OK:RISC_STORAGE_ASYNC_INVALID;
}
static void publish_async(void){
 // Preserve the complete checked sleep transaction through every async suffix.
 // Existing ordinary file and power-preparation prefixes retain their layout.
 state_api.prepared.base.sleep=api;
 state_api.prepared.base.sleep.terminal.power.volume.base.struct_size=sizeof(capacity_api);
 risc_storage_volume_api_v1_export_prepare *xp=&state_api.prepared;
 xp->base.export_tag=RISC_STORAGE_EXPORT_TAG;xp->base.export_version=1;
 xp->base.export_begin=export_begin;xp->base.export_read=export_read;xp->base.export_write=export_write;xp->base.export_sync=export_sync;xp->base.export_end=export_end;
 xp->prepare_tag=RISC_STORAGE_EXPORT_PREPARE_TAG;xp->prepare_version=1;xp->begin_prepare=export_begin_prepare;xp->prepare_step=export_prepare_step;
 state_api.state_tag=RISC_STORAGE_STATE_TAG;state_api.state_version=1;state_api.observe=observe_state;
 filesystem_api.fs_tag=RISC_STORAGE_FS_TAG;filesystem_api.fs_version=1;
 filesystem_api.dir_tell=fs_dir_tell;filesystem_api.dir_seek=fs_dir_seek;filesystem_api.metadata=fs_metadata;filesystem_api.file_truncate=fs_truncate;filesystem_api.replace_file=fs_replace_file;filesystem_api.recover_replace=fs_recover_replace;
 asynchronous_api.async_tag=RISC_STORAGE_ASYNC_TAG;asynchronous_api.async_version=RISC_STORAGE_ASYNC_VERSION;
 asynchronous_api.begin=async_begin_checked;asynchronous_api.submit=async_submit;asynchronous_api.collect=async_collect;asynchronous_api.end=async_end;
 package_api.package_tag=RISC_STORAGE_PACKAGE_TAG;package_api.package_version=1;package_api.submit_package=package_submit;
 download_api.download_tag=RISC_STORAGE_DOWNLOAD_TAG;download_api.download_version=2;
 admission_api.admission_tag=RISC_STORAGE_SESSION_ADMISSION_TAG;admission_api.admission_version=1;admission_api.begin_checked=async_begin_checked;
 capacity_api.capacity_tag=RISC_STORAGE_NATIVE_CAPACITY_TAG;capacity_api.capacity_version=1;capacity_api.submit_capacity=capacity_submit;capacity_api.check_capacity=capacity_check;
}
