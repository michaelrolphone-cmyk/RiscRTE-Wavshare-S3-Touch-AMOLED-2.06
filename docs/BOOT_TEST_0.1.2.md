# Waveshare 0.1.2 — black-screen investigation

Full initial image: `Waveshare-0.1.2-Home-0.15.0-boot-test-full-0x0.bin`, 8,388,608 bytes, flash address **0x0**. Target **Waveshare ESP32-S3-Touch-AMOLED-2.06 only**, not T-Watch or X4. No SD card or network is needed. As with 0.1.1, flashing overwrites the lower 8 MiB including NVS/settings. This is not a data-preserving update.

## Why another candidate

The hardware log reaches Home's first-frame and services-ready stages, but the user sees a completely black display. Those stages confirm software/transport completion, not panel readback. The installed CO5300 link is write-only. Physical display success is not established by those messages or by host tests.

Compared with Waveshare's pinned Arduino reference at `b099739ad0e33b34e5fbaae77f02bd84805d79a3`, the previous provider omitted the independent single-lane `0x02 / 0x2c` RAM-write-start command and used `0x32 / 0x2c` for pixel data. The vendor calls `writeAddrWindow()` to issue RAMWR, then `Arduino_ESP32QSPI::writePixels()` sends `0x32 / 0x3c` (write-continue). This candidate follows that sequence for each bounded row transfer, retaining CS across both pixel chunks. Register command/address/parameters are sent contiguously. Inversion-off and MADCTL RGB/rotation-zero are now explicit, matching the remaining vendor initialization steps.

This is a concrete protocol correction, but the user's physical root cause remains unconfirmed. The earlier decoder tests accepted the same assumed framing as the implementation; they did not independently prove compatibility with the panel. The revised decoder enforces the vendor RAMWR/WRMC sequence and exact initialization command order.

## What should happen

At panel startup, **a brief white pulse** is requested at 25% brightness for 250 ms using `ALLPON (0x23)`. That command bypasses the pixel framebuffer. The driver then restores `NORON (0x13)` and blanks the panel until Home's complete frame has been transmitted. Home and the hardware-test screen should then behave as in 0.1.1.

The pulse is enabled only for this boot-test composition through `CO5300_BOOT_PROBE=1`; ordinary provider builds do not pulse. It is a diagnostic, not a physical-success assertion. A visible white pulse but no Home image narrows the remaining issue toward RAM writes/pixel transport. No pulse and no image leaves initialization, physical signaling, power/reset and panel compatibility open. A missed 250 ms pulse is not proof that it never occurred; observe from power-on.

Only the display provider/version and its boot-test compilation flag are changed in the firmware payload. The native Runtime source/flags, shared Home 0.15.0, return module, board configuration and other providers/apps retain the previous selection. PMIC rail/charging settings are not guessed or rewritten. The schematic's ALDO2/DSI_PWR_EN path remains an item for readback if command/protocol correction does not restore the display.

## Flash and report

Replace `PORT` with the actual USB port. Close the serial monitor while flashing:

```sh
python -m esptool --chip esp32s3 --port PORT --baud 460800 write_flash 0x0 Waveshare-0.1.2-Home-0.15.0-boot-test-full-0x0.bin
```

No separate erase or filesystem upload is required. Use the same BOOT/PWR download-mode procedure as 0.1.1 if automatic connection fails. After flashing, restart with BOOT released, watch the panel from power-on, and save USB serial at 115200. Report whether the white pulse appears and whether Home subsequently appears. `RTE_SOURCE=5323d1e834bdcc8e5e9fb0e8f76c383e46626801` is deliberately unchanged: the repair is in the loaded display ELF, not the native firmware.

## Software evidence

Production panel code is exercised normally and with ASan/UBSan, both with and without the probe. The decoder checks initialization order, every pixel, separate RAMWR and WRMC transactions, two-chunk CS lifetime, first-frame brightness, wake restoration, and all startup I/O failures. Complete image assembly additionally validates the actual Runtime dependency graph, native exports and all 13 ELFs, verifies both independent/implementation SPIFFS readback, and rejects corrupted stores. These are software checks; hardware validation is pending.

Reference files in the pinned vendor repository:
- `examples/arduino/libraries/Arduino_GFX/src/display/Arduino_CO5300.cpp`
- `examples/arduino/libraries/Arduino_GFX/src/display/Arduino_CO5300.h`
- `examples/arduino/libraries/Arduino_GFX/src/databus/Arduino_ESP32QSPI.cpp`
