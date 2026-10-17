# Waveshare no-card Light-to-Deep repair

The 0.1.54 candidate repairs a generic Runtime serial-disconnect state bug over
the immutable 0.1.53 release. The user reported `Sleep Err Deep -3` on 0.1.52
with no SD card inserted and no serial transfer: Battery Status, return Home,
then an untouched sleep/wake loop. The earlier 0.1.53 correction addressed the
separate zero-duration untimed-sleep INVALID(-1) dispatch defect.

## Reproduced cause

The delivered Runtime's successful Light return calls serial disconnect for
HWCDC recovery. Disconnect latches cancellation even when no host, transfer,
handle or provider operation exists. Home's Hybrid timer path proceeds directly
to Deep without a service checkpoint. CpuPort observes serial exit safety as
false and returns BUSY(-3). The actual Runtime source fixture reproduces this
with no provider calls and fails when correct Deep entry is required.

The narrow repair clears only an idle protocol session's RAM synchronously.
Active, reentrant and retained-custody operations continue to require the
existing settled owner checkpoint. Sleep readiness guards are not bypassed.
This does not require a Home, app, SDK ABI or provider change.

The independent idle-mounted-SD readiness defect remains separately tracked.
Its absent-card control succeeds; it is not the established cause of this
reported no-card sequence and is not folded into this narrow candidate.

## Exact preservation and qualification

`released-baseline.json` records all 128 files and 62 ELFs extracted from public
0.1.53 factory bytes. Paired firmware and store match their standalone assets.
All 62 application/provider ELFs, manifests and boot grants remain byte-identical;
only `cohort.json` binds the rebuilt native Runtime and candidate identity.
Home and the retained power provider are independently rebuilt twice and checked
against the exact preserved hashes. Retained Battery source lineage is recorded
in `retained-battery.json`; no Battery source rebuild is required or claimed.

The source-owned native workflow builds the exact Runtime on ESP-IDF 6.1 and
GCC 15.2, runs focused regressions, admits the complete store through the real
loader normally and under sanitizers, verifies final IQ-linked memory fit,
round-trips the final factory and verifies every published byte. Synthetic
preservation/fault tests are software evidence; they do not make the factory
installation data-preserving. Factory installation erases internal saved data.
Hardware testing remains pending.

Baseline release:
https://github.com/michaelrolphone-cmyk/RiscRTE-Wavshare-S3-Touch-AMOLED-2.06/releases/tag/test-sleep-rebound-0.1.53

Active defect:
https://tasker-workboard.hazy-auk-4334.chatgpt.site/?task=eb70f59f-e7b1-49e4-a5bd-d63c3d59bf03
