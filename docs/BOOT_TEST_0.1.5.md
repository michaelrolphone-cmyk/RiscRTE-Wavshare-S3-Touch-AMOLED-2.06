# Waveshare 0.1.5 vendor-backed Home test

This full 8 MiB image at address **0x0** contains shared Home 0.15.0 and the
pinned vendor Arduino_CO5300 plus Arduino_ESP32QSPI stack that produced visible
output in standalone A/B. Generic Home display.output interfaces are unchanged.
The custom framed NativeSpi transport is not used by this panel provider.

**Waveshare only.** Full flashing overwrites firmware, settings and NVS in the
lower 8 MiB. It is not a preserving OTA update. Do not flash another device.
No SD card or network is required. Sleep remains disabled in this bring-up build.

Expected log: `PANEL_LINK transport=vendor-Arduino_ESP32QSPI
controller=vendor-Arduino_CO5300 native-spi=unused` (one line).
There is no ALLPON white pulse in this version. Report whether Home becomes
visible, touch/navigation responds, and provide the boot log including RTE_SOURCE.
Vendor SPI calls report no panel acknowledgement; successful software completion
does not prove visible output. Hardware recovery is **unverified** until tested.

Vendor source: waveshareteam/ESP32-S3-Touch-AMOLED-2.06 at
b099739ad0e33b34e5fbaae77f02bd84805d79a3. The staging script adds cleanup resource
tracking and a close method only; panel reset, initialization, transaction/CS and
pixel transfer code remains vendor source. PMIC registers are read, not modified,
matching successful A/B; the rail must already report enabled 3.3 V.

Use this run's build.json, SHA256SUMS.txt and DEVICE_COMMIT.txt to identify the
exact firmware. A build/test result is not physical qualification.
