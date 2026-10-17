# Actual 0.1.58 NS timeout: bounded Home evidence

The physical retest failed after a verified flash and successful SD initialization.
The browser reported an NS response deadline; no completed namespace enumeration
or file transfer is shown. The generic incomplete-install warning does not prove
that files were written. The previous .57 and .58 release assets remain immutable.

The log reports Home entry at 4,068,224 us and entry returned at 22,295,158 us,
with 154 lost records. The user reports the watch face stayed visible. These
observations do not distinguish a clean return, retention, sleep, or reboot.

## Timing and selected source

Runtime 4b3998f8091d1948a702a281757a1935d401ea4a,
`src/bootstrap/Runtime.cpp:1931-1948`, calls the app, shuts down native serial,
and only then prints the returned marker. The 18.226934-second marker interval
is not a measurement of the Home body alone. The exact public native build's
`main.cpp` compile command and forced `profiles/native-idf61-settings.h` do not
select `RISC_NATIVE_FAILURE_EVIDENCE`; `NativeFailureEvidence.h:3-14` defaults
it to zero. Thus the conditional pre-marker failure-evidence barrier is inactive
for this product, while the later unconditional exit barrier remains.

Watch b00d4e7d36fc69c8defd250a82f6af077c732137,
`apps/clock/crown.c:1223-1228`, accepts checkpoint OK and BUSY; every other
checkpoint value returns directly. Ordinary break/cleanup paths include health,
post-submit display status, alarm and provider-promotion refusal.
The selected native health callback itself always succeeds; Runtime health can
refuse when invocation authority is absent. Missing native crash evidence is a
healthy retry, so generic malformed-evidence branches are not claimed as reachable
physical candidates in this exact build.
Cleanup at lines 1505-1562 does not blank the completed display frame.

Presentation polls yield 1 ms until completion/failure or its 10 s/10,001-poll bound
(lines 330-373). Pacing yields only the remainder below 20 ms, in <=8 ms slices
(lines 461-479). Wave's retained vendor display queues 502 rows on submit;
`include/common/display.h:113-155` advances at most 32 rows per graph poll.
This requires repeated Runtime yields during normal presentation. Synchronous
provider/render callbacks can still delay the next explicit yield.

## Executable controls

Run `scripts/test_home_ns_boundaries.py` with exact Watch/System/Utilities inputs
listed by the workflow. All four controls pass normally and under ASan/UBSan:

- Sustained checkpoint BUSY: Home continues through modeled 30 s and 269 checkpoints.
- Forced health refusal: clean return at modeled 18,270 ms, all 41 grants released,
  completed face still visible.
- Forced post-submit display failure: clean return at modeled 18,227 ms, all 41 grants
  released, completed face still visible.
- Forced checkpoint CONTEXT: direct return at modeled 18,270 ms, 12 grants remain.

Each control freezes an exact copy of the last completed pixel buffer at its
return boundary and compares every byte and the completed-frame token after
`app_main` returns. If a health refusal occurs during an accepted transfer, the
snapshot is frozen when Home finishes draining that transfer, before cleanup.
The failed-frame control preserves the previously completed frame. All controls
also require nonzero modeled display brightness. This checks completed pixels
across the modeled return/cleanup boundary, not a physical panel.

The 18,227 ms injection point deliberately crosses the observed marker interval;
it is not calibrated hardware timing. Runtime/peripheral boundaries are modeled,
not the native settings scheduler. These controls exclude BUSY alone as a Home
exit trigger and demonstrate that a visible face does not identify the return
branch. They do not reproduce or identify the physical cause. Native NS delivery
while discovery owns storage requires the separate scheduler composition.

The inherited fixture sets `initial_default_entry=false`, so these controls skip
the cold-entry animation even though the cold-animation branch is compiled.
They exercise the settled Home loop, not an exact first-boot replay. The fixture
also supplies a null `failure_evidence` callback and absent crash AppData. Exact
.58 instead supplies a callable Runtime wrapper that returns false when its
backend is absent. Both let Home continue, but the null-callback fixture marks
evidence checked while the selected Runtime wrapper permits later retries.
These controls do not cover crash-record reading, acknowledgment, or spool I/O.

The initial and parameterized qualifications preserve the earlier replay records.
`pixel-preservation-qualification.json` and the eight current normal/sanitized
logs record the strengthened pixel comparisons and source dependency hashes.
The CI runner regenerates the fixture and runs both builds from pinned source.
