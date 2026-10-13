# Local source routing checkpoint toward 0.1.18

Publication is blocked. No hardware operation or flash was performed. This is
not a delivered or fully assembled successor image. 0.1.17 remains unchanged.

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

Docker stalls before creating any container, even a network-disabled local
image echo. Fresh real pinned-LittleFS native mount/source fault tests remain
blocked. Prior imported evidence is preserved but is not called a fresh run.
Full-image assembly/readback and final cohort update validation remain pending.

The immutable 0.1.17 rollback image SHA256 is
0406333e2d28942203cdc3b051cab0e6a4fc78c39d45129cdee16b07cac7ed05.
