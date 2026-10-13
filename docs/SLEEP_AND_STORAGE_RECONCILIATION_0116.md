# Local cumulative investigation checkpoint

The user reports that both tap and hold on Home do nothing, with no SLEEP ERR; Back works in apps. This rules out explaining the observation solely by the shared Home's short-release versus long-hold policy. No physical sleep root cause is yet proven. No hardware was accessed.

## Home acquisition and diagnostics

The assembled default.json requires input.power-key, power.sleep and display.power; boot.json grants each API1 at instance0. Shared Home capability_clients.c:7-32 acquires each independently; Runtime::acquire (Runtime.cpp:510-521) defines instance0 as a unique authorized match, not a physical GPIO number. Home's crown.c:1117 reads the separate key API, and :1258 requests manual sleep on bit2 after250ms. Its normal app invocation does not link portable_navigation.c. Settings/alarm/context cancellation can discard events, but no source evidence yet establishes that they explain this hardware report.

The production Waveshare power driver latches bit2 short release and bit1 long press in sample_key, and scheduler power_poll samples GPIO0 while active. The legacy key adapter merely forwards that function. Actual Home plus actual GPIO power provider tests still produce one native sleep request for100ms and zero for1000ms. Other peripherals and physical native sleep are mocked: this is software evidence only.

Shared Home source349c92d adds failure-only stage diagnostics for unavailable key/power/panel capabilities; blank brightness/acquisition/submission; checkpoint staging/abandonment; and selected wake restoration errors. It does not alter key semantics, polling, sleep/cleanup decisions, delays, grants or retained-state ownership. No extra diagnostic is emitted on the ordinary rendering path. Unavailable sleep capabilities receive an explicit visible capability error instead of silent optional absence. Fatal errors are logged without attempting unsafe display recovery.

The complete actual-Home fast-wake regression passes normally and with UBSan at240x240 and410x502. New injected brightness/acquisition and missing key/power/panel failures produce exact stages and preserve cleanup. Existing modeled frame/input timings and retention fences pass. The actual GPIO provider fixture also passes after the change. Target Home builds and Runtime ELF validation pass.

Local cumulative0.1.16 retains the expanded ABI3 layout, all25apps and34providers, with only default.elf and cohort.json changed from0.1.15. Normal and UBSan complete cohort admission each pass59ELFs with190cooperative yields and zero hardware/storage calls. Dual filesystem readback passes; eight free SPIFFS blocks remain. This candidate is held locally for evening testing, not uploaded or published. It is diagnostic, not a claimed physical repair.

## Storage: capability access versus hardware coupling

The compiled Files profile selects PORTABLE_FILE_BROWSER_APP. Apps/file_browser.c:1-3 selects file_browser_portable.inc; the older nonportable branch containing /sd/System/State/Applications/file_browser/Session.txt is excluded. Current build receipt files-nativeheight-0112/final/file_browser-build-record.json preserves that selection and does not enable PORTABLE_FILE_BROWSER_SOURCE_HANDOFF.

file_browser_portable.inc:245-259 fb_acquire selects generic capability and instance, then uses the common storage-volume table. Current product choices are storage.installed-files and storage.app-data.export. These are two capability-backed views, not separate SD and SPIFFS drivers in the app. No SD.begin, SD_MMC, SPIFFS or LittleFS call was found in these compiled app access paths.

A concrete limitation remains in file_browser_operations.inc:355-372 fbx_open: exported secondary files are directed to primary storage before opening, and primary handler paths receive /sd. Nearby handoff similarly prefixes /sd at file_browser_mount.inc:183. This follows the current T5FileOpenApi.h:37 absolute-SD-path contract; Runtime FileOpenRuntime.inc:25-30 validates that prefix and performs no filesystem I/O. It is a storage-specific handoff contract, not proof of direct hardware access. Existing generic file.open.source source-handoff support in shared Files cannot simply be enabled: this Runtime has no matching capability implementation.

Shared Canvas source lib/CanvasApp/canvas.c:243-259 has relative app-data reads via stat/read and optional volume-stream reads requiring /sd/. Those are capability operations, but the latter retains the SD path-policy assumption. The current preserved baseline model_viewer manifest/grants have storage.app-data only, so its optional volume/file.open path is not provisioned. The inspected current shared Canvas source is not claimed as a new reproducible build of the reused baseline ELF.

Runtime NativeAppData.cpp:66-77 mounts the explicit512KiB internal appdata partition with LittleFS, with formatting disabled; application stat/read/replace remains abstracted through storage.app-data. This backend does not depend on acquiring file.open or on Files being present. Key-value and explicit shared-data namespaces likewise remain distinct capability authorities. SPIFFS boot-store storage is not the writable app-data backend.

## Confirmed product omissions and next integration boundaries

The board DOES have SD. Full waveshare/hardware/board.json device12 describes sd,sd-memory-1bit with pins CLK2,CMD1,DAT0=3,DAT3=17. The cumulative candidate's selected board graph omits device12; its boot graph omits storage_sdmmc; its native ELF lacks risc_sdmmc_host_abi. The expanded native profile does not enable RISC_ENABLE_SDMMC.

Existing drivers/storage_sdmmc/driver.c:1-12 and :91 implement generic storage.volume@1 using the scoped SDMMC/GPIO host and board config; there is no device-model branch in apps. The provider's actual FatFs RAM-card tests passed again, including nine write interruption boundaries. Physical card mode, wiring/timing and sleep recovery remain unqualified. Current provider ELF is30516bytes before its manifest and filesystem overhead; adding it exceeds the current spare capacity after retaining the required four-block reserve unless further lossless packaging work is done.

Preserve internal app-data contents/authority and installed-file visibility while adding an independently selected SD backend. Do not replace private app-data with an SD-only assumption, silently migrate existing contents, gate app storage on file.open, or replace an existing Files view merely to expose SD. A generic source-aware handoff needs matching Runtime/provider support and receiver authority tests; it is not accomplished by renaming /sd or adding a device conditional.

Against the pinned25-app baseline, the cumulative set has all apps except LoRa messages (no LoRa hardware declared) and adds the bring-up diagnostic. Manifest requirement changes alone are not evidence of lost features: optional shared-data requirements and the distinct shared Home's retained-wake path need comparison against their exact compiled recipes. Files/Waterfall, Contexts/catalog, full-height Home, GPIO key latching and shared update apps remain preserved. Full SD integration is still pending; this checkpoint does not label storage parity complete.
