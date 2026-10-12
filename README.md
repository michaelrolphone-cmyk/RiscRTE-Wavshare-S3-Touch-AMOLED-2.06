# RiscRTE — Waveshare ESP32-S3-Touch-AMOLED-2.06

Device-specific drivers and integration for the canonical `RiscRTE-Watch` application. Both watches consume the same `default.elf` and `clock.elf` role artifacts; this repository does not contain a separate Home app.

## Physical providers

| Provider | Hardware | Public capability |
|---|---|---|
| `panel_co5300` | 410x502 RGB565 QSPI AMOLED, column offset 22 | `display.output@1` |
| `touch_ft3168` | FT3168 at 0x38, reset/IRQ, 12-bit coordinates | `input.touch.raw@1` |
| `rtc_pcf85063` | PCF85063A at 0x51 | `rtc.clock@2` |
| `power_axp2101` | AXP2101 at 0x34, active-high SYS_OUT key | `board.battery@1` |
| `motion_qmi8658` | QMI8658C, coherent milli-g samples and tap detector | `motion.accel@1` |
| `haptic_gpio` | GPIO-driven ERM motor, board-selected polarity | `haptic.effect@1` |

The initial display and battery implementations retain their deployed legacy power suffixes for older clients. Home 0.13.0 does not depend on those suffixes: generic compatibility providers in RiscRTE-Drivers expose independent `display.power`, `power.sleep` and `input.power-key` interfaces. Device configuration selects implementations; capabilities have no device prefixes.

AMOLED brightness uses the panel's brightness command, not a fictitious PWM backlight. The battery provider preserves factory charge and rail policy and only enables voltage measurement. The QMI driver uses bounded command handshakes and restores configuration before removing wake enrollment. The motor provides bounded pulse approximations, not identical DRV2605 waveforms. See `docs/MOTION_AND_HAPTICS.md` for wake/tap limitations.

## Build and test

```sh
python3 scripts/test_drivers.py --watch ../RiscRTE-Watch
python3 scripts/test_drivers.py --watch ../RiscRTE-Watch --sanitize
python3 scripts/build_drivers.py --watch ../RiscRTE-Watch --system ../RiscRTE-System-Apps --cc /path/to/xtensa-esp32s3-elf-gcc
```

CI pins the shared ABI/compiler, tests actual driver code against register/transport models, builds all selected ESP32-S3 provider ELFs, and checks the real Runtime loader. Ordinary builds do not generate or mutate source files. The native panel transport requires RiscRTE's generic Quad SPI extension.

## Integration status

Six physical providers have source, normal/sanitized host tests and target build support. ES8311/ES7210 audio, microSD, complete device packaging/provisioning, application parity and physical qualification remain in progress. The board does have a GPIO18 motor; the earlier statement that it lacked haptics was wrong. No LoRa/IR capability is advertised for absent hardware. Existing watch releases have not been replaced.
