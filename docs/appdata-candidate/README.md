# App-data and scene composition checkpoint

This is not a delivered firmware image. The delivered 0.1.8 source checkpoint
`d877062c739e1326f1e16f7468977ac3260225a8` and BIN SHA256
`7ce14678fb8e5c113ad55d96382e94270220088cb8640a5568faf2b9a99ea89a`
remain unchanged. No hardware was flashed.

The original 16 applications are default, clock, springboard, settings, bringup,
battery, calculator, stopwatch, alarms, countdown, wifi_settings,
frequency_generator, points_in_time, ble_scanner, ble_touchpad, and ble_buttons.

The candidate stages five more: timecard, audio_spectrum, contexts, lists, and
model_viewer. It has 21 applications, 28 providers, and 49 ELFs. The actual
Runtime graph and native-export/ELF checks pass normally and under UBSan with
zero hardware calls and zero storage calls. Removing the explicit app-data
backend rejects the graph with `app-data backend/namespace unavailable`.
These checks do not execute target app instructions or qualify hardware.
The production scene host passed 179 presenter/profile host executions; civil
clock raw/UTC read and retention scenarios passed with UBSan.

`software-checkpoint.json` records exact component source inputs, compiler
arguments, ELF hashes, native files, and admission results. The new composition
script validates the delivered store before copying it to a new output; it
rejects reused output directories. It pins each existing component owner.

## Real storage and scene dependencies

`native/appdata-candidate.ini` selects Runtime's existing paired 16 MiB app-data
layout, native TCP, entropy, HTTP, and IQ backends plus the existing vendor
display implementation. A single-job target build succeeded. It retains the
524,288-byte app-data partition. The empty offline LittleFS disk 2.1 image was
generated and remounted using Runtime's exact pinned core and matches expected
SHA256 `5f03c248f2de31c4da9ae8d9bc2033df064cee5e37694a9982f70fbb2f1d2ef0`.
It is for a future initial image only; boot does not format storage.

The scene host, compact-color presentation profile, and civil clock were built
from System `1aaf53e23ca9651a5cf9d1debe44941c9d7d0e58`. The scene host uses its
existing four-dependency raw-touch profile; native navigation is optional in
the provider source. Contexts 0.4.2 uses its shipping scene client, its original
shared-file maps, and the current Contexts service already in 0.1.8.

Lists and Model Viewer are copied unchanged from the qualified Watch 1.1.5
image. That full image hash was verified, its 111 store files were independently
decoded, and every one of the 65 files in the preserved-file receipt matched.
The two ELFs and their exact policies are separately hash-checked by the builder.
Lists uses namespace 62, scene, and civil time. Model Viewer requires display,
touch, and namespace 64; broader file browsing/import is a separate Files path.

## Remaining integration dependencies

* Shared catalog: consume the shared owner's qualified app.catalog Runtime and
  adapter. Remove generated catalog.c from all shared app link inputs, not just
  its references. Current component builds retain the universal original
  fixture solely as an intermediate link input. They must not be delivered.
* Files: preserve the 1.5.30 copied-table and Nearby custody fixes in System
  1aaf53e. Its adapter implements PORTABLE_CHECKED_STORAGE_RUNTIME, while the
  2c3f44d adapter implements native-height and retention. Neither current pin
  contains both sets. Shared-owner reconciliation is required before linking
  a feature-complete Files component. Also compose TCP/entropy/BLE sharing and
  its explicit owner/file export map.
* Waterfall: the unmodified recorded link recipe triggers the macOS Xtensa BFD
  assertion at elf32-xtensa.c:3299. Verify it using the Linux toolchain, as for
  the existing IQ/Contexts provider builds; do not mislabel this as a source bug.
* OTA Update / App Store: System Services/update/Policy.h defaults to the T-Watch
  repository and twatch-s3 identity. Provision an explicit Waveshare provider
  policy and paired cohort. Do not add device-name branches to shared apps or
  install the T-Watch-selected providers unchanged.
* Final image: await catalog/Files integration, assemble paired metadata and
  banks, verify capacity/readback and Linux ASan, then produce a distinct image.
  No app deletion or user-data partition reduction is part of this checkpoint.
* LoRa Messages: no LoRa radio is declared on this board.

## Runtime CI reconciliation

Runtime commit `815013e4b3c623e5b9b788a0062d8b5e864e935c` changes only
test/test_native_startup.py and test/spi_radio_test.cpp. The startup fixture now
expects the existing post-validation RTE_SOURCE line. The radio fixture accesses
legacy SPI fields through the additive table's base prefix. Production behavior
and ABI are unchanged. All eight startup variants and the normal/UBSan radio
regressions pass locally. The Mac ASan run stalled and was stopped. Local Clang
radio runs suppress unrelated existing unused-field/unused-variable warnings.
Full Runtime CI is not claimed green. Publication of the checkpoint was blocked
by automatic approval review pending explicit user authorization.

Files follow-up: all five Runtime-table extent variants and all twelve RGB/paper
Nearby ownership/cancellation/retention cases passed under UBSan. Only the
temporary Mac test runner was adjusted for Bash3.2 empty arrays and a vendored
SHA unused-function warning; shared source was not edited. Waterfall still
asserts with localized libgcc symbols. The cached local Linux container never
started a process, so no Linux qualification is claimed.

The one authorized publication retry and private Drive backup upload were both
rejected by automatic approval review. Exact actions/reasons are recorded in
publication-status.json. Verified incremental Git bundles and candidate evidence
remain in the local checkpoint backup; no remote backup success is claimed.
