# 0.1.58 serial recovery candidate

Reserved as `test-sd-apps-0.1.58`. This additive recipe starts with the independently
audited public 0.1.57 factory, internal store and complete 45-file SD archive.
The released 0.1.57 source recipes, artifacts and active catalog association are
unchanged. Runtime 0.4.10 is selected at
`4b3998f8091d1948a702a281757a1935d401ea4a`, carrying the native readiness fence
and first-failed barrier diagnostics. Final build admission rejects missing pins.
Component CI and the exact native product build remain separate gates.

The candidate keeps five internal applications (including the hidden clock
navigation shim), 38 internal providers, 22 external app images, exact boot
policy, grants and logical data mappings. Every retained byte is checked against
the public 0.1.57 inventory. Only `cohort.json` and the explicitly locked
`installed-apps` provider may change. That provider embeds the versioned feed URL,
so a 0.1.58 core feed requires a new URL-bearing ELF; other provider and app images
remain unchanged. Three independent catalog builds across the behavior and
version-bumped Runtime sources match: 85,896 bytes, SHA256
`35131eb0d78c9d483710699eccfe15c8304ba1741691d03d7ab9b0d4818c47d0`.
Its manifest is unchanged. Pre-native packing changes exactly two files,
`cohort.json` and that ELF, retaining 109 internal files and all 45 SD files
byte-for-byte with 791 empty 4 KiB blocks. Native cohort packing is remeasured.

The native qualifier retains exact-source fresh native compilation, complete
43-ELF admission, namespace-authority negative control, actual linked platform
selection, DWARF capacity, workspace placement and IQ checks. It also replays the
14 actual provider/Home boundary tests against the selected sources. The separate
full native lifecycle/serial scheduling regression runs normal and sanitized
fixed cases inside the same-process native qualifier. Dedicated CI also runs the
released baseline and fixed-source fence-disabled negative control. No modeled host test establishes physical SD,
target instruction execution or the complete hardware failure cause.

The reported 0.1.57 failure is a clean serial STAT -3 followed by Home return and
a generic native retention barrier. Boundary tests show that clean -3 alone does
not retain Runtime or force Home to return. This candidate must retain these
negative controls and cannot weaken owner, custody or exit-safety checks.

The current on-device firmware is 0.1.57 and its observed failure remains open.
Recovery installs the repaired 0.1.58 Runtime first, then requires explicit serial
reconnect before guarded known-LoRa transfer and per-file readback. The existing
0.1.57 catalog association is unchanged. No payload transfer on the faulty .57
Runtime, SD clearing or automatic overwrite is selected.
