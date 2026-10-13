# Waveshare 0.1.4 — framed SPI repair candidate

Target: Waveshare ESP32-S3-Touch-AMOLED-2.06 only. File `Waveshare-0.1.4-Home-0.15.0-boot-test-full-0x0.bin`; full 8 MiB initial image, flash at 0x0. This overwrites lower-8-MiB firmware/NVS/settings. No separate erase, filesystem upload, SD card or network is required. Not for LilyGO T-Watch or X4.

## Hardware evidence

The owner reported A/B working and C/D not working in DISPLAY-LINK-TEST-1. The original Waveshare backend illuminated this panel at both 80 and 40 MHz, whereas the old native raw SPI path did not at either 40 or 5 MHz. This isolates a native-transport-path failure. The exact internal mechanism has not yet been confirmed by a captured waveform. ALDO2 was already enabled at 3.3 V and reset readbacks succeeded; those earlier changes did not restore the display.

## Corrective implementation

The CO5300 provider now uses generic framed SPI transactions. Its command/address fields use the ESP32 hardware command/address phases, submitted together with the one-lane register payload or first four-lane pixel payload. Continuation chunks have no repeated header and retain CS until the row is complete. The header is no longer emitted through a separate data-only SPI transfer.

The native Runtime supplies an append-only `exchange_frame` extension to `spi.bus`. It uses SDK polling, explicitly routed GPIO-matrix pins and exclusive SDK ownership before asserting CS, corresponding to the relevant behavior of the hardware-proven vendor path. Header values, panel registers and physical pins remain outside the generic transport. It validates owner, table extent, token, bit counts and payload size. Payloads are copied to native DMA storage; completion has an 8 ms cap per call within the begin budget. A timed-out poll retains its descriptor, buffer and CS for cleanup, instead of reporting success or freeing active DMA memory. Legacy ordinary/three-wire transfer functions remain available.

The immutable native source is `97336e63ce1eac40364893e0ddf5b9fe61b648b7`, in Runtime PR 72. The panel implementation, matching public headers, tests and image assembly are in Waveshare PR 1. No board-specific Home variant was introduced. Shared Home 0.15.0 and the existing test application set are retained.

This is the normal integrated Home boot-test composition, NOT the A/B/C/D standalone comparison firmware. It requests the existing brief white illumination probe, then starts Home. It still omits the same unfinished radios/audio/SD/alarms/sleep integration as 0.1.3. Automatic sleep remains disabled.

## Flash and identify

Close the serial monitor, substitute the actual serial port, and use the existing BOOT/PWR procedure if automatic download mode fails:

```sh
python -m esptool --chip esp32s3 --port PORT --baud 460800 write_flash 0x0 Waveshare-0.1.4-Home-0.15.0-boot-test-full-0x0.bin
```

The boot log should contain:

```text
RTE_SOURCE=97336e63ce1eac40364893e0ddf5b9fe61b648b7
PANEL_LINK transport=framed-spi header=hardware-command-address completion=polling
```

Capture USB at 115200 from restart. Report whether the white probe and then Home appear. PMIC/register/transport logs do not establish physical illumination. Hardware confirmation of this corrective image remains pending.

## Validation

Native tests inspect actual SDK command/address/payload descriptors on both SPI controllers, continuation CS, missing extension, bad lengths, owner/token/deadline checks and failed polling cleanup. Physical provider tests exercise every pixel, initialization, power/readback failure paths and rejection of the old raw-only API. Normal and sanitizer runs are followed by full target compilation, Runtime/ELF admission against the actual native exports and independent filesystem readback. See the completed build's evidence and receipt for the checks that ran; this document does not substitute for the workflow result.
