# 0.1.53 controlled delivery

The new recipe starts from the published 0.1.52 factory, tag source
3368c0719597116fcb4b583b4a596f41a79d5263, with every extracted file digest
pinned in released-baseline.json. It changes only battery/driver.elf,
battery/manifest.json and cohort.json. Home, Settings, Springboard, panel,
alarm service, boot authority and every other payload remain byte-identical.
The historical 0.1.52 recipe and qualification files are hash-guarded unchanged.

The corrected power0.1.3 source is compiled twice with pinned GCC15 and a
reviewed flattened public-header selection. Both outputs must be identical,
match the pinned digest and pass the production ELF validator. Loader-metadata
compaction proves loaded-section, relocation and symbol equivalence. No target
instructions or hardware are exercised by this compiler/loader proof.

Local preflight on the exact released 128-file store packs deterministically
into 0x550000 bytes with six empty blocks. The changed provider is 6,268 bytes,
SHA256 1834f708fdd7ef725db16a0719b21cd41816cf5b60a867826b017722eb1dd4be.
The public common Home remains 617,424 bytes at its original SHA256.

The release-branch workflow runs strict provider and actual Home policy tests,
normal and ASan/UBSan, reproduces the unchanged common Home twice, builds the
native firmware from exact sources, checks final IQ layout and admits every
ELF in the final paired store normally and under sanitizers. Final factory
extraction proves preservation. Source, build, CI and checksum evidence are
bound to the exact commit. The approved publisher uploads a draft, verifies
all remote bytes and only then makes the prerelease public.

The factory image erases internal saved data. It is not a preserving update
kit. Physical retesting is required for crown Light/Deep/Hybrid sleep, tap
settings, nearby alarms and wake sources; software evidence alone cannot
establish that every reported spontaneous wake is fixed.
