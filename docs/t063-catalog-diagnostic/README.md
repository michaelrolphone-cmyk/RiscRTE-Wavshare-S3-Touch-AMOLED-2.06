# Waveshare 0.1.41 catalog diagnostic

This is a diagnostic build based on exact 0.1.39. It does not claim to fix the physical Apps unavailable cause. The existing Springboard failure screen now shows the catalog failure stage, numeric result and index. Report those two added lines after swiping Clock to Springboard; a photo is sufficient. Repeat after changing the Clock face if that changes the result.

Only Springboard and its version/cohort metadata change. Native firmware, Home, all other apps/providers, policy grants, data namespaces and partition layout are byte-preserved. Original shared Springboard, layout, launch protections, one-second recovery and terminal custody fences remain.

The factory BIN is a full 16 MiB offset-0 image and overwrites saved internal data. The preserving kit is for exact 0.1.39 only. It requires a fresh full-device readback, verifies the active source image and lays out writes to the inactive bank. Verify firmware/store/bank-state readbacks before writing the separate OTA selection sector LAST. Do not erase the device. The kit performs no flashing. The SD card is unchanged.

Software checks cover failure stages, changed-failure redraw, recovery/cleanup, callback-free presentation, normal/sanitized lifecycle, full-feature Springboard and byte-identical .39 baseline reproduction. These are software checks; hardware remains unverified.

The separate T023 provisioning candidate is not included. Do not apply the preserving kit to 0.1.40 or any version other than exact 0.1.39.

Interpretation for the reported lines:
- `acquire`, result 0: Runtime declined the catalog grant while still reporting healthy custody.
- `interface`, result -1: the returned interface did not satisfy the expected contract.
- `allocation-failed`, result -1: allocation for the catalog rows failed.
- `snapshot` or `snapshot-after`: result is the native snapshot return code; result 0 with an error means snapshot metadata failed validation.
- `row`: index identifies the rejected row. Result 0 means returned metadata failed validation; a nonzero result is the native row-read result.
- `duplicate-row`, result -1: duplicate launch identity.
- `generation-mismatch`, result 0: the publication changed during the copy.

Do not infer the hardware cause until the actual stage/result is observed.
