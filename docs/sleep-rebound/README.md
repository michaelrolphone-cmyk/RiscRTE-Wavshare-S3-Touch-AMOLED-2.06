# Untimed power sleep correction

## Exact released defect

Waveshare 0.1.52 retained power provider 0.1.2 (5,948 bytes,
SHA256 `7ba073e30bab4a00a9c146af6e6e594ae381729e7102a9eea58e3ba491999127`).
The released tag is `3368c0719597116fcb4b583b4a596f41a79d5263`.
Its qualified producer source `92be7bd0b3666dfdf63d468f9206762cd1804053` forwards
`light()` and `deep()` to their timed callbacks with duration zero.
The same defect is present on product main `ff558f13c2b97c3d40a3c04d0b9f3d0103fc7038`.

Released Runtime `9f8d67029181f6cd064e247aa949a295854fc494`,
`src/ports/esp32s3/CpuPort.cpp`, rejects duration zero in
`gpioLightSleepFor()` and `gpioDeepSleepFor()` before hardware entry. This is
required by `sdk/driver/RiscTimedSleepV1.h`; zero is never indefinite.
The owned untimed callbacks and wake-set suffix are separate APIs.

Released shared Home `8132d73c828c0e4763f6c89a3d6a4a883314056a`,
`apps/clock/watch_sleep.h` and `watch_alarm_sleep.h`, selects the ordinary
untimed callback when there is no motion wake set and no alarm deadline.
Consequently crown-only Light or Deep can return INVALID (-1) immediately.
Hybrid can sleep successfully for its configured Light interval, then return
INVALID instead of entering untimed Deep. Home correctly restores the display
on refusal, producing an apparent wake and a sleep error. This is a verified
failure path, not proof of the user's selected settings or every hardware wake.
The defect predates .52; no newly introduced commit is claimed.

## Correction and boundary

Provider 0.1.3 dispatches untimed Light and Deep to their corresponding owned
GPIO callbacks, checking their actual prefix size. Timed methods reject zero;
wake-set methods continue accepting zero as specified by their distinct ABI.
There is no Runtime or shared Watch behavioral change, no retry loop, wake-source
suppression, PMIC policy change, or weakening of retained-cleanup barriers.

The .52 display ELF remains the corrected 0.2.1: 9,632 bytes,
SHA256 `514e919d65be8c9642cdefbce5efe0daad276185148dbace218ae81beb896d78`.
The old display Deep -7 repair and retained-wake grant are already present.
T-Watch's power provider uses the correct untimed callbacks and has no matching
forwarding defect.

## Regression evidence

`tests/test_power_untimed.c` includes the actual production power provider.
Its timer fakes enforce the exact Runtime zero-duration contract. The fixture
fails without this change at its first untimed Light assertion (exit 134),
then passes with the change. It covers ordinary Light/Deep, positive timers,
invalid zero timers, zero-duration wake sets, older prefix-only tables, absent
callbacks, claimed input token, and polarity. Existing provider fixtures
continue covering retained results, rollback and peripheral cleanup.

Run:

```
python3 scripts/test_drivers.py --watch /path/to/RiscRTE-Watch
ASAN_OPTIONS=detect_leaks=0 python3 scripts/test_drivers.py --watch /path/to/RiscRTE-Watch --sanitize
```

Ten standalone provider fixtures pass normally and with ASan/UBSan. LeakSanitizer
is disabled only because the execution sandbox's ptrace environment does not
support it. These host checks do not establish hardware sleep/wake behavior.
Full firmware must be built and qualified by exact-source GitHub CI before
candidate publication. Hardware retest must record sleep mode, tap wake setting,
on-screen stage/code and elapsed time before unsolicited wake.
