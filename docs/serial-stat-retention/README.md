# 0.1.57 serial STAT failure: bounded reproductions

The installed `test-sd-apps-0.1.57` user test reached Home and enumerated
writable namespaces 2 and 12, then reported `STAT failed (-3): unavailable`.
Home later returned with the generic native-retention barrier. The device log
also reported 154 lost diagnostics. Software/publication qualification did
not establish this hardware path; hardware acceptance failed.

## What these tests establish

`tests/serial_stat_home` and `scripts/test_serial_stat_home.py` compile the
actual product SD provider/FatFs and the selected Runtime's `RuntimeFiles` and
`StorageFilesVolumeAdapter`. Four cases run normally and under ASan/UBSan:

- An active copied session returns UNAVAILABLE without retention. STAT succeeds
  again after the session ends.
- A prepared sleep transaction returns UNAVAILABLE without retention. STAT
  succeeds after checked resume.
- Refused owner custody during metadata access returns RETAINED and is unsafe
  to release. The test does not weaken this guard.
- An unavailable media-I/O state returns UNAVAILABLE without retention.

The actual production Home controllers are compiled at 410 by 502 pixels with
fast wake, generic preferences, atomic writes, automatic provisioning and crash
reporting. Three further sequences run normally and under ASan/UBSan:

1. Three real provider UNAVAILABLE results during a copied session followed by
   successful STAT results: Home continues and cleans up normally.
2. Three injected BUSY service-checkpoint results followed by successful STAT:
   Home continues and cleans up normally.
3. The first sequence followed by a separately injected RETAINED checkpoint:
   Home returns immediately, preserves grants and performs no further modeled I/O.

All 14 cases passed at this checkpoint. The readiness test uses modeled sector
transport, synchronization guard and copied worker. The Home test uses modeled
peripheral services and injects Runtime service-checkpoint results. It does
**not** implement native lifecycle scheduling, real USB transport, native
custody pinning, Xtensa instruction execution, or physical hardware. It is a
causal boundary test, not a reproduction or fix of the complete device failure.

## Exact inputs and replay

- Product source: `653b667f6876551161c5c4727e69936f32b53683`; production provider
  is unchanged from firmware producer `aa0664c2905abb264a6b07f35d027b4879562c68`.
- Runtime: `070d5c7e347f74357f2e8843312409315aca5762`
- Watch: `b00d4e7d36fc69c8defd250a82f6af077c732137`
- System Apps: `bb0cadf3cec3445a64e11513b47b2676f3fdd92d`
- Utilities: `4fdcad2495c33fe63f5f6faca9b11ced3c739a5b`

Run `python3 scripts/test_serial_stat_home.py --runtime RUNTIME --watch WATCH
--system SYSTEM --utilities UTILITIES --sdk SDK --output OUTPUT`, where SDK is
the exact merged provider SDK used by the product build. The helper retains the
generated Home fixture, commands, each test log, and all 205 compiler-observed
non-system source/header hashes in `OUTPUT/qualification.json`. It changes only
the inherited test fixture's constant API table to permit callback selection and
renames that fixture's main; production Home sources are included unchanged.
LeakSanitizer is disabled for the host's ptrace incompatibility; address and
undefined-behavior sanitizers remain enabled and fatal.

The accompanying receipt normalizes local paths but preserves hashes/results.
No production code, dependency pin, firmware, release asset, or catalog
association is changed by this test checkpoint.
