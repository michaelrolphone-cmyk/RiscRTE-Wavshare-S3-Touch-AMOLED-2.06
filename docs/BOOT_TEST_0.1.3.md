# Waveshare 0.1.3 — explicit panel power and reset verification

Target: Waveshare ESP32-S3-Touch-AMOLED-2.06 only. Full image `Waveshare-0.1.3-Home-0.15.0-boot-test-full-0x0.bin`, 8 MiB, flash address **0x0**. This initial image overwrites lower-8-MiB firmware/settings/NVS. It is not a preserving update. No SD card or network required. Use the same BOOT/PWR procedure as 0.1.2.

## Hardware report driving this revision

The user still saw no display on 0.1.2, including no reported ALLPON pulse. Its longer panel startup and subsequent services-ready log show that the probe code ran through software; they do not establish physical illumination. The earlier command correction did not recover visible output.

The supplied Waveshare schematic connects panel J3 pin21 (`DSI_PWR_EN`) to AXP2101 ALDO2 through R10. Panel VCI/VDDIO are on VCC3V3. The previous build initialized the display before its PMIC and never established or read back ALDO2. This is a missing power-sequencing prerequisite and a candidate cause, not a measured diagnosis of the user's board.

## Changes

A board-selected AXP2101 ALDO2 provider exposes generic **power.rail@1**. The CO5300 driver depends on that service, not `board.battery`, a private PMIC suffix or an application board check. The generic interface can have implementations on other hardware; chip/address/channel policy stays in this device provider.

Startup first reads the PMIC chip ID and ALDO2 enable/voltage registers without writing. The panel then asserts reset LOW and verifies physical GPIO readback. With reset held, the rail provider sets ALDO2 to 3.3V and enables it, preserving every unrelated bit/register. It rereads both registers and refuses readiness on mismatch. Already-enabled 3.3V configuration incurs no write. An enabled output at another setpoint is disabled only while its setpoint is changed, then enabled again. Reset is released HIGH and physically read back before any panel commands.

Only register0x90 bit1 and register0x93 low five bits are writable in the rail driver. No charging current/voltage, battery model, thermistor, DCDC, other LDO or IRQ policy is changed. The existing battery driver retains its original VBAT-ADC enable write, but uses short I2C address leases rather than monopolizing the PMIC for its whole lifetime. Failed lease release retains its token for cleanup.

The command-only white probe now lasts 750ms at25% brightness, then returns to normal Home. Shared Home0.15.0, its return module, native Runtime source/flags and the original board pin mapping stay unchanged. Automatic sleep remains disabled. There are now10providers /14ELFs /30store files.

## New USB diagnostics

Capture serial at115200 from power-on, including these prefixes:

- `PANEL_POWER stage=discovered` and `stage=before`: actual chip-register enable/setpoint before correction.
- `PANEL_POWER stage=after aldo2_enabled=1 configured_mv=3300`: register readback, **not an analog measurement of voltage at the connector**.
- `PANEL_RESET stage=assert ... readback=0`, followed by `stage=release ... readback=1`: physical ESP GPIO input readings.
- `PANEL_PROBE phase=all-on ... duration_ms=750`, then normal mode and Home.

If a readback fails, the driver reports failure instead of reporting ready. A valid PMIC/reset readback plus a black display still leaves connector power, electrical signaling and panel command compatibility open. No software log claims photons appeared.

## Flash

```sh
python -m esptool --chip esp32s3 --port PORT --baud 460800 write_flash 0x0 Waveshare-0.1.3-Home-0.15.0-boot-test-full-0x0.bin
```

No separate erase or filesystem upload. Do not flash to T-Watch or X4. Observe from power-on for the white pulse and Home; return the complete new USB log even if still black.

## Validation and references

Tests execute actual rail/panel/battery source normally and under ASan/UBSan. Cases cover cold-disabled rail, wrong setpoint, already-correct output, exact bit-preserving register writes, ignored writes/readback mismatch, I2C failures, retained-release failure, missing generic supply, supply refusal and stuck reset LOW/HIGH. The full image validates the real Runtime graph/native exports/14ELFs, two independent filesystem readbacks and missing/corrupt-module refusal, including a missing power-rail provider.

Hardware-root-cause confirmation and visible-display recovery are pending. These remain development test images, not stable releases.

Primary references: Waveshare schematic `ESP32-S3-Touch-AMOLED-2.06` (AMOLED J3/R10 and PMIC blocks), and vendor source `b099739ad0e33b34e5fbaae77f02bd84805d79a3`, `examples/arduino/libraries/XPowersLib/src/XPowersAXP2101.tpp` (`enableALDO2`, `setALDO2Voltage`) plus `REG/AXP2101Constants.h` (0x90/0x93,500mV+100mV steps). The vendor HelloWorld example relies on existing PMIC state rather than explicitly programming this rail.
