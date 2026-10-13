# Local source routing checkpoint toward 0.1.18

Publication is blocked. No hardware operation or flash was performed. This is
a fully assembled, offline-qualified full-initial image, held for evening delivery.
It has not been delivered. 0.1.17 remains unchanged.

## Isolated source checkpoints

- Runtime d766b448184d373f8a5b9d94161f484c0d2c099c, based on db0ad9b.
  Reuses existing e263221 / 64c8e52 source handoff and native mount code.
- System Files 0e9f7401903b93ec4c32e44e8dafddc81a9a4de3, based on e90ce6d.
- Utilities Model Viewer 79a2743436397c760f4e48dbf6364a039de0d815, based on fc0bdbb.

Files selects configured generic installed-files, app-data-export and volume
capabilities. Missing grants are skipped; absent media uses provider readiness.
Inactive roots retain their grants during copying and remote mount activity.
Cancel/copy completion selects the exact source root. Source-enabled local and
Nearby Open always stage into the existing Runtime source token API; the former
primary-storage.volume `/sd` bypass is removed from those compiled branches.
Model Viewer consumes token reads, preserves builtin/saved model choices and the
original parser/rendering, and does not retain a caller-owned handle or mount.

The staged store preserves all 25 apps, 35 providers and every prior grant;
only Files/Viewer ELF+manifest and boot policy change from 0.1.17. All other
payload bytes, including Home diagnostics, are identical. Viewer compaction
checks allocated sections, relocations and symbols. `stage_source_candidate.py`
records the complete inventory and build receipts.

## Evidence and limits

Native firmware build succeeds with source backend enabled and all seven mount
fences. Files and Viewer target ELFs structurally validate. Modeled full-store
admission validates 60 ELFs with zero hardware/storage calls. Local evidence is
under workspace `cumulative-source-0118`.

- Runtime: 29 source handoff scenarios normal and UBSan, including actual Files
  controller, receiver return, cancelled capture, unsupported handlers, full
  storage, Home, failed load/init, resident/legacy paths and retained I/O.
- Disk source backend: normal/UBSan fault tests, 12 MiB bounded streaming,
  capacity reserve, short I/O, failed-read privacy, symlink refusal, false-success
  open, no retry after terminal retention, cold cleanup and reopen.
- Files: 68 source-controller cases across RGB/paper/scroll/three-root profiles;
  nine mounted-peer regression cases under UBSan; three-root pairwise copy,
  missing capability, absent/reinserted media, exact cancel return and release
  retention normal/UBSan.
- Canvas: 12 real-entrypoint cases under UBSan, including short token reads with
  a builtin.obj basename collision, saved models, legacy SD, and retention.

Runtime disk tests use a documented macOS-only test interception shim because
GNU linker wrapping is unavailable. Production sources are unchanged. This is
not a GNU/Linux or hardware qualification claim. macOS ASan executions stall;
UBSan results are recorded separately.

## Final qualification

The full 16 MiB 0.1.18 image was assembled from product f8a45035479868cd0a38c35c9043443598898724
and Runtime d766b448184d373f8a5b9d94161f484c0d2c099c. Its SHA256 is
0c0a582990cf5e319bbaf48e10b22f592c7573b164109b86fcd8be0668be5f1c.
Original and independent SPIFFS readback agree with every staged payload. Bank
state hashes/CRC and untouched regions are checked. Physical spare capacity is
133 pages / 8 blocks. The AppData image is byte-identical to 0.1.17.

Normal and UBSan cohort validation under the new Runtime both admit 60 ELFs,
with 194 cooperative yields and zero hardware/storage calls. Update policy
checks actual payload metadata and rejects wrong identity, ABI, layout, capacity
and downgrade; an empty feed performs no I/O.

Fresh GNU/Linux native tests now PASS normal and ASan+UBSan: six real pinned
LittleFS mount cases, four NativeFileSource cases, source-disk faults, and all
29 Runtime source-handoff scenarios. The production harnesses are unmodified.
Exact Git archives and vendor hashes identify the copied inputs. The image is
python:3.11-bookworm at sha256:fb8fe532522e2338cd30855e9c46387c29e21ed7c0e06da81e08eeef112d75b2.

Docker diagnosis: the API proxy stalled in host file-sharing registration
(`grpcfuseClient.Add`), before the engine received the start request. A restart
was performed only after inventory showed no unrelated containers. Plain
containers recovered, but host bind-mount creation still stalled. Docker's
supported archive-copy API avoided that path: sources were copied into a
network-disabled, no-mount container. It exited zero, evidence was copied out,
and only this task's test resources were removed. Docker settings and unrelated
containers were not modified.

**OTA from 0.1.17 is rejected.** Its Runtime lacks file.open.source. Actual
0.1.17-to-0.1.18 cohort admission returns `app provider unavailable`; removing
only the two new declarations and matching grants in a diagnostic copy makes
admission pass, isolating the cause. That copy was deleted and was never
assembled. No admission bypass was added. The final unpublished release index
is USB-only; the paired payload is retained solely for qualification. Full
initial provisioning erases internal settings/AppData. Physical SD, display
and key/sleep behavior remain untested.

The existing 512 KiB AppData partition backs private capture, with a 64 KiB
reserve. Available capture space is smaller; large files may return NO_SPACE.
No resize, format or automatic fallback was added. Delivery remains held until
2026-10-13 23:30 UTC; no upload, push or hardware flash occurred.

The immutable 0.1.17 rollback image SHA256 is
0406333e2d28942203cdc3b051cab0e6a4fc78c39d45129cdee16b07cac7ed05.
