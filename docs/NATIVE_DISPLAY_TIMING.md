# Opt-in native display timing

Compile the device-build Runtime with `RISC_PERFORMANCE_TRACE=1` to include the
native backend timing aggregates. Ordinary builds have no timing clock calls,
counter updates or marker. The hardware API, 40 MHz SPI clock, paired-row
protocol, framebuffer ownership, failure custody and shared UI are unchanged.

The enabled native executable retains the string
`RISCRTE_VENDOR_DISPLAY_TIMING_V1` through a live-code reference. Verify this
marker in the exact ELF and firmware being packaged, and record their hashes.
The marker must be absent from a trace-disabled control build. App stage tracing
is selected separately by the shared application build.

After a reproducible gesture, send the existing diagnostic command `perf`
followed by a newline. Capture the complete existing `RTE_PERF` begin/end output.
Do not retrieve diagnostics during the measured gesture. No telemetry is printed
from the row/SPI hot path. Runtime's existing replay checks writable capacity,
drains at most 64 bytes per poll and preserves partial-write/disconnect behavior.

The recorder's phase aggregates have these device-build meanings:

| Phase | Count | Value sum | Duration sum in microseconds |
| --- | --- | --- | --- |
| 34 | Completed native frames | Accepted rows | First accepted row through last row transfer completion |
| 35 | Completed native frames | Paired windows | Synchronous window commands and pixel writes |
| 36 | Completed native frames | Paired windows | Time before/between those transfers, including row copies and scheduling gaps |
| 37 | Completed native frames | One per frame | Sum of each frame's maximum paired-window transfer time |
| 38 | Completed native frames | One per frame | Sum of each frame's maximum pre/inter-transfer gap |
| 39 | Aborted partial frames | Accepted rows | First accepted row through first close attempt |

For a complete frame, phase 34 duration equals phase 35 plus phase 36 duration.
Do not add frame span and transfer span together. Divide phase 37/38 duration by
their frame counts for the mean of per-frame maxima; they are not a global p95
or the worst observed maximum. Aggregates are cumulative from Runtime trace
configuration, so subtract complete snapshots for a bounded interaction window.

At 410×502, every completed frame has 502 rows and 251 paired windows. Timing
needs one clock sample at the first row and two around each paired write:
503 timer reads and five aggregate writes per complete frame. No per-pixel
clock reads, allocations, locks, formatted messages or USB writes are added.
All measurements use the Runtime monotonic microsecond source. Transfer timing
begins after the native pair copy and includes vendor address-window writes,
pixel byte swapping, polling transfer start/end and transaction setup. Gap
timing includes pair preparation and time given back to other work. Native
first-row time is after application submit; use the separate application
submit/complete trace to measure that extra interval.

Closing a partial frame records one abort even if native cleanup refuses and
has to be retried. A successful complete frame produces no abort on close.
Runtime-disabled recording produces no clock calls even in a trace-enabled
binary. No change is made to cancellation or cleanup decisions.

## Verification

```
python3 tests/test_vendor_native.py
python3 tests/test_vendor_timing.py
ASAN_OPTIONS=detect_leaks=0 python3 tests/test_vendor_native.py --sanitize
ASAN_OPTIONS=detect_leaks=0 python3 tests/test_vendor_timing.py --sanitize
```

The timing regression extracts the actual native timing/row/close source. It
checks all 502 rows, exact transfer-plus-gap accounting, enabled/disabled clock
work, invalid rows, one abort across failed-close retry, and no double count
after completion. The original native regression checks pixel ordering and
bus/CS/reset cleanup custody. Host timings are synthetic; actual on-device
gesture timing remains unmeasured until the owner captures a trace.

## Decode an owner capture

```
python3 scripts/decode_display_perf.py serial-capture.txt
python3 scripts/decode_display_perf.py serial-capture.txt --json
python3 tests/test_display_perf_decoder.py
```

The decoder requires complete `begin`/declared records/all 64 phase counters/`end`
snapshots. Incomplete or malformed captures fail explicitly. Other ordinary
serial lines are ignored. Ring overwrite is reported; partial application
summary batches are omitted rather than joined across invocations.

Application phase 8 records contain a high-byte tag and a 24-bit payload. Tags
0x40–0x4e are five consecutive count/total_ms/max_ms triples: render, poll,
catalog refresh, accepted-submit to observed-completion, and ordered input-edge
age. A payload of 0xffffff is potentially saturated and is treated as a lower
bound without calculating a mean. Application summaries are reset windows,
emitted no more than once per 2 seconds while work exists, plus a final flush on
exit. Native and Runtime counters are cumulative since trace configuration.

Render includes surface acquisition/clear and cooperative pumps/capture through
present entry, and excludes present copy/submission. Poll includes waits,
provider work, optional services and routing; it is not just touch polling.
The separate display stage measures asynchronous ownership latency from
accepted submit to observed completion. Phase 4/5/6 milestones each occur once
per invocation and permit a first-frame timestamp comparison when all relevant
records remain in the ring. The decoder labels counts/units, reports missing
data, and never infers frame rate by adding or inverting overlapping spans.

The .44 device profile selects a 64-record history ring to keep the reserved IQ
SRAM bank intact. All 64 cumulative phase counters remain available. The shorter
history window can overwrite records sooner; inspect lost counts and capture
a complete trace soon after a short, reproducible interaction while remaining in
Springboard. Application batches contain 15 records every two seconds; later
idle batches or launch traces can overwrite earlier gesture history. No complete-history
claim follows from a syntactically complete snapshot.
