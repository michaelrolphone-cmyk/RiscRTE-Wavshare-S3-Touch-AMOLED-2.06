# Home confirmation liveness and first-exit checkpoint

## Confirmation while native work is busy

Phase 3 uses the settled turn's existing `service_checkpoint` result. A healthy
BUSY result defers provider promotion and paired confirmation for this turn.
Input, rendering, yielding, cancellation and native service progress continue.
The first wait and the 5,000 ms threshold each emit one diagnostic. This is a
diagnostic deadline, not a timeout that terminates Home. After an OK checkpoint,
the existing promotion and confirmation checks run unchanged. Quiescent refusal
still returns through cleanup; the native strict storage veto is not weakened.
The wait state resets at entry and wake, alongside the deferred phase.

The actual baseline Home reproduces BUSY -> refused paired confirmation -> clean
return with its last completed pixels and token unchanged. The fixed Home stays
responsive during BUSY, confirms after release, and retains cancellation and
terminal retention behavior. `confirmation-matrix` contains 28 normal and
ASan/UBSan cases at 240x240 and 410x502. The fixture runs production Home against
modeled Runtime/peripheral services and skips cold-entry animation. It does not
execute the native confirmation callback or prove the physical .58 failure.

## First outer exit checkpoint

Home attempts one bounded RAM-only checkpoint at the first outer return, cleanup
jump, or foreground-loop break in each invocation. The record is
`WATCH_HOME_EXIT line=NNNNN`, resolved against the exact producing crown.c.
A compound condition identifies that outer route, not a unique nested cause.
Normal navigation is also an exit and may be recorded while authority permits it.

The existing optional diagnostic-checkpoint API derives identity in Runtime.
The app does not acquire providers, allocate, or write live serial output.
It copies 26 bytes synchronously. The first attempt is never overwritten or
retried, including when the getter is absent or authority denies it.
Runtime rejects queued, revoked, retained or busy lifecycle authority, so this
is not a guarantee of evidence after every retention path. The record survives
app return and console handoff in RAM; reset and power loss discard it.
The record is separate from native serial event-ring observations and ordinary
eight-message diagnostic chatter. Pending serial work may suppress live lines
without preventing this RAM-only capture.

The checkpoint fixture exercises actual Home at both display sizes in normal
and ASan/UBSan builds, including first-attempt preservation, invocation reset,
absent/denied authority and the inherited lifecycle suite.

## Target footprint

`final-footprint.json` measures the complete change: 554,744 bytes, up 1,888 from
the exact released 552,856-byte Home. Dynamic imports/exports are unchanged and
Runtime ELF structural admission passes. `footprint.json` preserves the earlier
diagnostic-only prototype measurement; its stack prologues are not a total call
chain bound. Exact native product composition and physical testing remain separate.
