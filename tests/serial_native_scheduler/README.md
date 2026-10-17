# Native lifecycle / serial ownership regression

`scripts/test_native_serial_scheduler.py` composes actual Runtime, RTEF1 serial
endpoint, RuntimeFiles, native settings discovery/maintenance, CpuPort, Wave SD
provider and FatFs. Sector transport, NVS and deterministic worker scheduling are
modeled. The fixture derives from pinned Runtime test sources, verifies their
hashes before adaptation, and retains the generated source, compile commands,
compiler-observed input hashes and complete per-case logs.

Every case uses its own new card and process. There is no reuse of prior card
state or cached compiled objects. `--expect baseline` omits the optional serial
readiness callback. It works with the released Runtime and with the fixed Runtime
as a fence-disabled negative control. `--expect fixed` installs the production
`NativeSettingsLifecycle::exitSafe` readiness callback.

Normal and ASan/UBSan runs assert:

- Baseline continued discovery: STAT during a live copied session returns clean
  `-3`; a later session-closed, still-pinned dispatch returns `-6` and the Runtime
  explicitly retains serial custody.
- Baseline immediate return after `-3`: Runtime drains and exits cleanly.
- Fixed continued discovery: checkpoint returns BUSY without dispatch, retains
  the queued request, and returns successful `STAT 6 4` only after the session and
  native pin are released.
- Fixed immediate return: shutdown cancels the queued request and exits cleanly.

The negative control verifies the serial fence is causally relevant to the
reproduced scheduling defect. It does not establish that the device's complete
generic native-retention message followed this exact sequence. Production Home
instruction execution, physical SD and USB behavior remain separate acceptance.
The existing fourteen provider/Home boundary cases stay separate and unchanged.

Complete prior baseline/fixed logs are in
`docs/serial-stat-retention/native-reproduction/`; new CI artifacts contain a
fresh replay rather than relying on those records. LeakSanitizer is disabled
because of the local ptrace-host incompatibility. ASan and UBSan are enabled with
fatal recovery disabled.
