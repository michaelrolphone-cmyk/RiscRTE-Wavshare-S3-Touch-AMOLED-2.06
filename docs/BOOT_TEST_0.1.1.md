# Waveshare 0.1.1: shared Home composition

Complete image: `Waveshare-0.1.1-Home-0.15.0-boot-test-full-0x0.bin`.
Flash at **0x0**, Waveshare ESP32-S3-Touch-AMOLED-2.06 only. The image is 8 MiB.
**Initial flashing replaces factory firmware and settings in the lower 8 MiB.**
It is not a preserving update. Keep the previously delivered 0.1.0 image and a
factory backup as fallbacks. The original backup and BOOT/PWR recovery procedures
are in `BOOT_TEST_0.1.0.md`.

```sh
python -m esptool --chip esp32s3 --port PORT --baud 460800 write_flash 0x0 Waveshare-0.1.1-Home-0.15.0-boot-test-full-0x0.bin
```

Replace PORT with the actual USB port. No separate filesystem upload, SD card or
Wi-Fi credentials are required. Native USB serial diagnostics remain at 115200.

This successor consumes the exact same canonical Home 0.15.0 application pair
as T-Watch 1.2.0. The main Home binary is unchanged from Waveshare 0.1.0;
`clock.elf` is now a 1,232-byte return module instead of an 866,992-byte second
copy of Home. Its return delegates to the configured default through Runtime's
normal child lifecycle. The shared stager supplies both roles, preserves the
board's supported capability grants, and records the application byte identities.

The watch face, face picker and HARDWARE TEST screen are unchanged. Swipe across
Home to open diagnostics; MOTION starts accelerometer readings, VIBRATE requests
a brief pulse, BACK TO HOME restores the face. Unset RTC time is not fatal.

This is a packaging/integration successor, not new peripheral enablement. It
retains the first boot-test feature selection and disabled automatic sleep:
radios, audio, SD storage, alarms and Contexts are still omitted. The existing
square layout remains centered on the taller display. Physical boot and power
behavior have not been verified by the build/host tests.

CI rebuilds the native Runtime, shared app roles and selected providers; executes
the real return-to-default lifecycle and shared Home tests; admits all 13 ELFs
against the actual native exports; checks normal/sanitized board/dependency
admission and both independent/implementation SPIFFS readback. The image,
source pins, validation logs and `shared-home-staging.json` are one artifact.
