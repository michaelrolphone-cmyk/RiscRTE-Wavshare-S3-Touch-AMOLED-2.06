# RiscRTE — Waveshare ESP32-S3-Touch-AMOLED-2.06

Device-specific drivers, hardware description and integration for the shared `RiscRTE-Watch` Home application. The app is not forked here: both watches use the same `default.elf` and `clock.elf` role artifacts.

## Implemented driver backfill

| Provider | Hardware | Interface |
|---|---|---|
| `panel_co5300` | 410x502 RGB565 QSPI AMOLED, column offset 22 | `display.output@1`, brightness and watch power suffix |
| `touch_ft3168` | FT3168 at 0x38, 12-bit coordinates, reset/IRQ | `input.touch.raw@1` |
| `rtc_pcf85063` | PCF85063A at 0x51 | `rtc.clock@2`, time and minute-resolution alarm |
| `power_axp2101` | AXP2101 at 0x34, active-high GPIO10 SYS_OUT key | `board.battery@1`, key and sleep suffix |

The power driver preserves factory battery charging and rail policy. It enables VBAT measurement but does not rewrite charging current, charging voltage, thermistor policy or battery-model registers. The panel driver keeps its controller commands in the ELF and requires the generic Runtime Quad SPI extension (`RiscRTE` commit `2d906c5c0f412b2d0957b91ff153a1a293128a8c`). It does not use a fictitious PWM backlight for AMOLED brightness.

## Validation and build

```sh
python3 scripts/test_drivers.py --watch ../RiscRTE-Watch
python3 scripts/test_drivers.py --watch ../RiscRTE-Watch --sanitize
python3 scripts/build_drivers.py --watch ../RiscRTE-Watch --system ../RiscRTE-System-Apps --cc /path/to/xtensa-esp32s3-elf-gcc
```

CI pins the shared ABI and compiler, runs the actual driver source against register/transport models with sanitizers, builds four loadable ESP32-S3 ELFs, and runs the Runtime loader validator. Panel tests compare every pixel in full-frame and wake presentations and exercise every startup I/O failure. These tests are not physical-device qualification.

## Remaining device integration

QMI8658 motion/tap wake, ES8311/ES7210 audio, microSD, complete system-provider/app provisioning and a paired flashable firmware image are not complete in this first driver backfill. Hardware-supported parity is not yet achieved. No LoRa/IR/haptics capabilities are advertised for absent hardware. The shared Home initially preserves its square layout rather than reflowing to fill the taller screen.

The source migration record retains the original T-Watch source identity and the Waveshare vendor reference identity. One-time readable import scripts record how inherited driver semantics were adapted; the resulting C sources are checked in, not generated during ordinary builds.
