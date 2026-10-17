# Waveshare 0.1.56 complete core provisioning

Published 2026-10-17. Software qualification and independent public-byte audit
passed. Hardware acceptance is pending.

## Exact delivery

- [Public release](https://github.com/michaelrolphone-cmyk/RiscRTE-Wavshare-S3-Touch-AMOLED-2.06/releases/tag/test-provisioning-0.1.56)
- Immutable producer: `907b9551b0d8208a7f979b0a722a7a47618e0402`
- [Product PR 7](https://github.com/michaelrolphone-cmyk/RiscRTE-Wavshare-S3-Touch-AMOLED-2.06/pull/7)
  merged as `b9862e1379813a0914d4926ef59a3feb6fcf656a`, preserving the cumulative
  `f20b971` main additions. The merge is not the binary producer.
- [Release CI](https://github.com/michaelrolphone-cmyk/RiscRTE-Wavshare-S3-Touch-AMOLED-2.06/actions/runs/39007526468/attempts/2)
  used the successful attempt-1 native artifact. A transient empty release list
  after creating the exact draft caused the first publisher attempt to fail;
  a failed-job-only retry verified and resumed that draft. No asset or tag was
  replaced. The native artifact's own provenance correctly remains attempt 1.
- SHA256SUMS: `656bf05f3d326d0bc45d402340c425734675dadf8639f5aa9a298ad64a8f3655`
- Factory, 16,777,216 bytes:
  `b343bf219999b5f801f6fc4b025e61e45224699c2cc89ef7dc9296c54a680ddc`
- Store, 5,570,560 bytes:
  `5b0ba40efd64f40115041c013c8e1d77e8709c68324dd43c47ccdba0438eef47`
- [Firmware catalog](https://riscrte.com/#firmware), release ID:
  `RiscRTE-Wavshare-S3-Touch-AMOLED-2.06:test-provisioning-0.1.56`, revision 1.
  Its uncached firmware verifier reports available, checksum verified and
  orchestrated Flash available. This is download/format verification, not a
  physical flash or device acceptance result.

## Common Home and retained payloads

Home 0.19.0 is 552,616 bytes, SHA-256
`5797b757e228f2055f4fda3384659e91830f77ff03a636f9b3f605aeca8ace0d`.
Watch source is `2be519c2047b2323e4d399c1de19b0591dc87c59`, merged by Watch PR 7
as `53282b569f5f2e2c7f55979c82b2eacad83dde30`. Independent local builds, exact-head
CI, merged-main CI and the final factory-extracted Home match. All 11,140 calendar
ring tuples and 1,632 complete rendered frames remain exact under normal and
sanitized tests. The atlas codec and ring symmetry changes are lossless.

The baseline is the exact public 0.1.55 producer `1606e707`. The complete new
store contains 132 files and 64 ELFs. All 124 unrelated payloads, including 61
non-Home ELFs, are byte-identical. Settings, Springboard, the Wi-Fi footer repair,
alarm repair and sleep lifecycle payloads are retained. Only boot/cohort metadata
and Home change; the catalog and internal package providers add four files.
Previous release recipes and the released 0.1.52 bytes remain immutable.

## Capacity, admission and feed evidence

Independent factory extraction reproduces the published firmware/store, every
store file and every retained-payload check. The unchanged 0x550000 SPIFFS store
uses 20,307 pages, leaving 93 free pages and six whole free blocks; the required
four-block reserve passes. The actual final native selection has USB PHY enabled,
diagnostics disabled and 22 platform tables within capacity 32.

Linked DWARF confirms the platform capacity and a 15,208-byte package workspace.
The 288-byte boot view and 2,792-byte serial workspace are in retained PSRAM;
the package workspace selects internal 8-bit heap. The final linked 64 KiB IQ
bank reservation and static-memory checks pass. These proofs do not measure
physical heap availability or hardware behavior.

Normal and ASan/UBSan production-loader factory admission validate all 64 ELFs
with no hardware/storage calls. The 0.1.55 preserving transition correctly
rejects Home's new grant to already-owned namespace 6 before ELF admission. An
authority-only causal control admits all 64 ELFs; the control is not packaged
and the Runtime guard is unchanged. No preserving update kit is supplied.

The [maintained core feed](https://raw.githubusercontent.com/michaelrolphone-cmyk/RiscRTE-Wavshare-S3-Touch-AMOLED-2.06/provisioning-index/native-packages-v1.json)
is byte-identical to the public release asset, SHA-256
`09f081253b1f6c706b4f3c26aae67dda85d8601d9d625326af5619b581a78ac2`.
Its complete `boot_profiles.core` inventory has 132 files and 64 ELFs. Production
controller tests parse it and select the immutable image URL, size and digest
exactly once. The separate dynamic `apps` list is empty. All required core bytes
are internal; there are no core SD mirrors. The existing optional external LoRa
payload policy remains unchanged.

Source Atlas exact-source fallback supported pinned textual inspection. Matching
complete compiler-index coverage was unavailable, so these results do not claim
a complete compiler-resolved cross-repository call graph.

## Installation and remaining physical checks

Use the catalog's full factory image at offset 0 only after backing up and
accepting erasure of saved device data. Do not flash firmware and store assets
independently. Follow the release's TESTING.txt for native Home/touch, preference
persistence, app loading, alarms and sleep/wake, first-start Wi-Fi/SNTP/core
provisioning, interrupted-download recovery and serial-file isolation.

Physical acceptance is still pending. The separate mounted-SD Deep-readiness
defect is not fixed in this release. Broader reported Wi-Fi freezes also need
candidate-specific retesting. Catalog entries retain these known limitations.
