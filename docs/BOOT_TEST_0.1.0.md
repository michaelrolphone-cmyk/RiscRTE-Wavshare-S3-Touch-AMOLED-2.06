# Waveshare first-boot test 0.1.0

Target: Waveshare ESP32-S3-Touch-AMOLED-2.06, with 32 MiB physical flash and 8 MiB octal PSRAM. Not for LilyGO T-Watch or X4.

Image: `Waveshare-0.1.0-Home-0.14.2-boot-test-full-0x0.bin`.
This is a complete 8 MiB initial flash image for address **0x0**: bootloader, partition table, native Runtime and internal SPIFFS with all selected app/provider ELFs. The generic native build declares a 16 MiB accessible flash region; the test only uses its lower 8 MiB. It does not depend on files in the upper physical flash.

**Initial flashing replaces factory firmware and erases the lower 8 MiB, including NVS/settings. This is not a preserving update or paired OTA package.** Keep a backup of the factory image before flashing. No SD card or Wi-Fi credentials are required. Do not flash `firmware.bin` alone at address zero.

## Flash

Use a USB data cable and close any serial monitor that has the port open. Substitute the actual port for `PORT` (for example `COM5` or `/dev/ttyACM0`).

```sh
python -m pip install esptool==4.11.0
# Optional but recommended: preserve all 32 MiB of the factory flash first.
python -m esptool --chip esp32s3 --port PORT --baud 460800 read_flash 0x0 0x2000000 waveshare-factory-backup.bin
# Write the one complete initial image; a separate erase_flash is unnecessary.
python -m esptool --chip esp32s3 --port PORT --baud 460800 write_flash 0x0 Waveshare-0.1.0-Home-0.14.2-boot-test-full-0x0.bin
```

Use 115200 baud instead of 460800 if the connection is unreliable. Leave flash mode/size/frequency overrides unset: use the image's verified native header.

If automatic connection fails, fully power off, hold **BOOT**, then power on to enter the ROM downloader. Release BOOT once the port appears. After flashing in forced download mode, fully power off and restart with BOOT released. Waveshare documents a PWR hold of at least six seconds to power off, then a PWR press to power on. Do not confuse BOOT with a reset button.

Vendor reference: https://www.waveshare.com/wiki/ESP32-S3-Touch-AMOLED-2.06 (FAQ: flashing failure / PWR and BOOT).

## What this test contains

The shared Home **0.14.2** is compiled in RiscRTE-Watch without a Waveshare-specific application variant. Its existing watch faces and picker render in a centered 410x410 area with matching touch mapping on the 410x502 screen. Screen gutters remain black. This is preserved-square layout, not full-height reflow.

A blank or invalid factory RTC no longer prevents Home from reaching its first frame. Unset time remains visibly unset; this test does not invent current time or include the full time-settings app. Battery percentage can be unknown until the PMIC has a valid reading/model.

Swipe across the Home face to open **HARDWARE TEST** in place of the full Springboard. Hold the Home face to use the existing face picker. The diagnostic screen has RGB bars, uptime, physical touch coordinates and battery/RTC readings. Tap **MOTION** to start accelerometer reads, **VIBRATE** for a short motor pulse, and **BACK TO HOME** to return. Optional motion/haptic providers are not started until requested. Moving the watch should change the reported XYZ acceleration; pressing VIBRATE should produce a brief pulse. An unavailable test is reported on-screen and through USB diagnostics.

The Home Wi-Fi shortcut also opens this diagnostic screen, explicitly labeled `RADIO AUDIO SD SLEEP OFF`. It does not claim to be Wi-Fi settings. This package deliberately omits Wi-Fi/BLE, audio, SD storage, alarms, Contexts, and system sleep services. Automatic sleep remains disabled. Keep the display on only as needed during bring-up; use PWR to turn the watch off afterward.

The selected drivers are CO5300 display, FT3168 touch, PCF85063 RTC, AXP2101 battery/key, QMI8658 motion and GPIO haptics, plus GPIO/I2C infrastructure and the generic power-key compatibility adapter. Hardware configuration selects their pins. All application capability names are generic.

## First hardware checks and logs

Connect a USB serial monitor at **115200**. The firmware uses native USB Serial/JTAG and emits `RTE_STAGE`, `WATCH_WAKE`, `WATCH_CLOCK` and `WATCH_TEST` messages. Save the whole log beginning at power-on, not just the last error.

Check: cold boot reaches the face; touch opens the diagnostic screen; tapping VIBRATE gives one pulse; MOTION produces changing readings; BACK TO HOME restores the face; power-off/on still boots. Do not interpret unset time or an unknown battery percentage alone as a boot failure.

If the panel stays black, the complete USB boot log distinguishes firmware startup, PSRAM/bootfs admission, provider activation, application entry and frame presentation. Successful compilation and host tests do **not** establish physical boot. This is the first hardware-test candidate, not a hardware-qualified release.

## Software validation

The build recipe recompiles both shared Home roles and all selected physical/compatibility providers. It checks every selected ELF against the actual native firmware's export table and production Runtime loader; runs complete board/dependency admission normally and with ASan/UBSan; unpacks the SPIFFS using both the implementation and an independent decoder; reruns admission on recovered files; and rejects missing providers and corrupted app bytes. The merged image's partition table, offsets and contents are checked. `build.json` records exact source commits and file identities.

The generic Home entry-point tests cover missing alarm and retained-wake services, unset RTC, first-frame sequencing, and cleanup. Diagnostic entry-point tests cover all controls at 240x240, 410x502 and 502x410 with optional hardware present/absent and asynchronous frame completion. These use hardware doubles; physical timings, power consumption and target instruction execution remain to be checked on the watch.
