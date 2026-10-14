# T063 cumulative startup candidate .37

Compose from exact published .36 (SHA256 af789153d58cd1bc2c262f7d32cb1f225cd7d0426c859a43d772d3deb99f115b). Preserve native c258c4ba144247b6eaa4c6f28675ffccec582fe1, T054 atomic preferences, Home, Settings, all other apps, grants and partitions. Replace only alarm-service (0.4.11) and Springboard plus cohort metadata.

Alarm source: Utilities fix/t063-wave-alarm-startup, 03adae46fa9448720321ad27efd344fadd3e8507. Production wave-startup-busy profile explicitly selects ALARM_STARTUP_BUSY_RETRY. Only typed BUSY during pre-anchor storage reads is deferred. Genuine I/O and write failures retain prior behavior. Nine startup phases reproduce the old block and recover with the fix; existing Watch/X4 alarm regressions pass. Actual compacted ELF passes Linux target-loader relocation checks.

Launcher source: System fix/t063-wave-catalog-startup. Its initial failure previously latched an empty launcher indefinitely. It now retries once per second and resets stale interaction state on recovery. 164 controller/adapter cases with ASan/UBSan and pixel parity pass. The exact physical first-request failure remains unconfirmed; diagnostics distinguish acquisition/interface and publication failure. No device flashed or hardware qualification claimed.

scripts/t063/build_springboard.py replays the qualified T054 build command against the shared checkpoint and normalizes/compacts its ELF. scripts/t063/assemble.py verifies the exact .36 baseline before composing and asserts only five store files change. Full store admission and exact-baseline preserving update tests must pass before release.
