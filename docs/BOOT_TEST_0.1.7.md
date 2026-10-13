# Waveshare 0.1.7 — real Springboard and time setup

Waveshare ESP32-S3 Touch AMOLED 2.06 only. Erase the lower 8 MB before writing this full BIN at 0x0. No 0.1.7 hardware verification is claimed.

Preserves shared Home 0.15.0 and the vendor paired-row display path that displayed Home after reboot in 0.1.6. Startup color probes remain. Manual-CS cleanup now retains ownership until pin reset succeeds.

Open Springboard from Home. The real shared launcher lists Home, Settings, and Hardware test. Settings provides Date & Time editing with an explicit SAVE and RTC readback; an unset RTC stays unset until the user saves. The time conversion policy matches the existing shared Home: RTC UTC+08, displayed America/Denver. Use Settings Back to return to Springboard, then Home. No guessed current time is written.

The former springboard.elf and wifi_settings.elf diagnostic aliases are removed. Wi-Fi and broader app/service parity are outside this image's scope; no working Wi-Fi settings entry is advertised. Actual source pins, image hashes and graph/ELF validation are recorded in build.json.
