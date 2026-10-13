# Local cumulative SD and Home event-trace candidate

This supersedes the diagnostic scope of0.1.16 but is held locally until2026-10-13 23:30UTC. No hardware or publication operation was performed. It does not claim a physical fix for Home's nonresponsive crown.

## Home event evidence

Shared Home e6d2a61 extends failure-stage diagnostics with a24-message-per-invocation transition budget. crown.c clock_key_trace/clock_key_read report unique key acquisition and sleep capability availability, classified short-release/long-held receipts, startup and wake discards, arming interval, foreground decision, alarm/context suppression and sleep entry. clock_alarm.inc routes alarm-entry discards and modal reads through the same wrapper. The API does not expose raw physical press edges; the logs explicitly describe gesture events rather than inventing edge evidence. No diagnostic is emitted for a zero-event poll. There are no new clock reads, waits, allocations, grants, render gates or background tasks.

Normal and UBSan complete Home tests at240x240 and410x502 cover delayed key acquisition, a fresh default invocation receiving a stale child short/long gesture, held-input suppression, normal manual sleep, alarm cancellation, retained cleanup and a100-call budget stress. The model's previous frame/input timings remain unchanged. These cases model invocation return and late activation; they do not emulate physical target timing or execute a hardware app-to-Home navigation. The actual Waveshare GPIO provider plus Home test still observes bit2/one sleep request for100ms and bit1/no sleep for1000ms. Hardware report remains unexplained pending the bounded trace from evening testing.

The actual assembled default.json and boot.json are checked for exactly one API1 grant at instance0 for input.power-key, power.sleep and display.power; Runtime admission validates their full provider graph and target images.

## SD device/provider/native integration

The expanded native profile now enables RISC_ENABLE_SDMMC and retains risc_sdmmc_host_abi. The selected board includes device12 from the existing hardware descriptor, with CLK2,CMD1,DAT0=3,DAT3=17. The existing generic storage_sdmmc/FatFs provider is mapped to storage.volume@1 instance12. Files and Model Viewer receive that capability without removing any prior grant; Model Viewer has no file.open grant, demonstrating that backend authority is independent of file-opening UI authority. No shared app file-access code or device-model branch was added.

The existing Files UI still selects its installed-files and exported-app-data roots. This checkpoint completes native/device/provider binding and authority, not the separate addition of an SD browser root. Storage app-data remains the original512KiB internal backend; it is not silently moved to SD. File access and backend selection are separate concerns.

Provider tests use real FatFs and a RAM card: present-card operations, absent card then insertion/removal, bad card metadata, corrupt media, read failure, nine uncertain-write boundaries, owner checks, power-down preparation/cancel and retained cleanup. Normal and UBSan pass without formatting or blind write retries. Native SDK-shim tests cover allocation/init/slot/card/read/write/sync/close/reset failures; CPU-port tests cover native ownership/pin/token custody; worker tests cover copied arguments and context boundaries. These are not physical SD qualification.

Packaging preserves25apps and adds one provider, yielding60ELFs. All existing ELF files except the diagnostic Home and Contexts are byte-identical. Contexts metadata compaction preserves every loaded section, entrypoint, global/weak symbol and retained relocation; its original ELF and equality proof are kept outside the store. JSON is compacted without changing values, apart from explicit SD device/authority additions and cohort identity. The approved ABI3 partition sizes and512KiB app-data remain unchanged. Final normal and UBSan cohort admission passes with zero hardware/storage calls; independent and original filesystem readback also pass.

## Queued backend-neutral handoff repair

Current file_browser_operations.inc fbx_open uses file.open.source when enabled for secondary/non-volume roots, but the primary storage.volume branch constructs /sd+path. file_browser_mount.inc:175-183 similarly constructs /sd for remote handoff. Runtime FileOpenRuntime.inc:24-30 validates only absolute /sd paths under the existing file.open@1 contract. Thus both producer and broker require coordinated repair; changing app strings alone is incorrect.

Preserve existing source-token authority and remote mounting semantics. Implement/qualify the matching generic file.open.source capability in Runtime, bind a source token to its authorized volume/path and receiving handler, enforce cleanup/revocation/retention, then route all supported Files roots through that source descriptor rather than a backend-name condition. Retain a legacy fallback only for a source that actually satisfies the old SD contract. Receivers such as Canvas must consume the source capability while preserving private relative app-data access. Remote handoff must retain its mount/source lifetime and cancellation behavior, not silently copy into an assumed SD destination.

Add SD to Files through a generic configured root selector while retaining installed files, exported app-data and Nearby; do not introduce a second storage implementation or replace an existing root. The inspected compiled access paths contain capability calls, not SD.begin/SD_MMC/SPIFFS/LittleFS calls in shared apps.
