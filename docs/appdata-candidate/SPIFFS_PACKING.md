# SPIFFS packing diagnosis and lossless fix

The preserved source candidate is 126300c044c60298bdece9cdefbbb85a50b1d9b7.
Its 102 files exactly match boot.json, board.json, 21 admitted app manifests/ELFs
and 29 provider manifests/ELFs. No duplicate-content groups, extra staged files,
or empty files were found. Payload is 3950310 bytes. No file contents changed.

## Proven cause

The installed mkspiffs 0.2.3 and a fresh ARM64 build of its exact upstream source
both fail at timecard.elf. Upstream main.cpp:156-187 reads and submits one byte
per SPIFFS_write call. The failed image contains 15569 live pages, 3840 deleted
pages and only 31 free pages. Timecard stops at 78592 of 143832 bytes; the two
Model Viewer files have not yet been added. This is allocation churn, not stale
files or a requirement to remove app code/assets.

The complete file set needs exactly 15993 live data/index pages. The existing
0x510000 partition has 1296 blocks of 4096 bytes, 256-byte pages, one lookup page
per block, and 19440 allocatable pages. Reserving four blocks leaves 19380 pages.
All partition offsets, bank sizes, app-data capacity and native code stay intact.

## Applied offline-only repair

`tools/mkspiffs-write-batching.patch` changes only the file-copy loop: read and
write bounded 8192-byte chunks, including an exact final remainder, and reject
short writes as well as negative returns. It changes no SPIFFS implementation,
format, geometry, GC configuration, filenames, file contents, or native runtime.

`scripts/build_batched_mkspiffs.py` exports immutable upstream source objects at
mkspiffs 112d65368043f01dd86813cb84e41b1159a34f6b (release 0.2.3), with SPIFFS
f5e26c4e933189593a71c6b82cda381a7b21e41c. It applies the small patch only in a new
output directory, builds the Arduino ESP32 meta4 format, and records tool/source
hashes. It does not modify the supplied checkout. Source: https://github.com/igrr/mkspiffs
and its pinned https://github.com/pellepl/spiffs submodule.

## Verification

The patched tool packs the complete store at its unchanged 5308416-byte size.
The installed, unmodified packer unpacks every file byte-for-byte. Runtime's
independent SPIFFS decoder also returns exactly all 102 original file bytes.
Native physical-capacity inspection passes:

| Metric | Pages/blocks |
| --- | ---: |
| Live pages | 15993 |
| Deleted pages | 563 |
| Total occupied pages | 16556 |
| Free pages | 2884 |
| Entirely free blocks | 192 |
| Page headroom after four-block reserve | 2824 |

Additional partition space required for this candidate: **0 bytes**. This is
measured physical image occupancy; it is not a promise that arbitrary future
apps of a particular byte size will fit.

The final reproducible-tool build emits the same complete image as the initial
batched experiment. Nonempty files of 1, 250, 251, 252, 8191, 8192, 8193, 16384 and
32769 bytes pass independent exact readback. An empty-file probe remains rejected
by native validation because upstream stores its uninitialized size sentinel;
production manifests have no empty files. The change does not relax validation.
Normal and UBSan whole-cohort admission from the unmodified packer's extracted
store pass for all 50 ELFs, with zero hardware/storage calls.

Complete bootfs SHA256:
85b9d70e3dd9a2e1f2f57be123a7b05876e5e7b73706db8e5f9aa69d616609f4.
This is a verified bootfs component, not a merged flash image. Final cohort/bank
binding and unfinished app composition remain separate. No flashing, partition
changes, publication, or upload occurred.
