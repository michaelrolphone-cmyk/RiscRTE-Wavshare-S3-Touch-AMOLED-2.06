# Waveshare 0.1.26: restore the shared T-Watch Springboard

The 0.1.25 integration replaced the validated shared artifact with a new System Apps 088c88b build (175,704 bytes; SHA-256 348324d4133752e2fb8023995b6e71b8f7db592e6ca5f20bc45711321362578b). That selection was wrong. Its changed Nova presentation path caused the reported hardware regression.

Restore the exact shared Springboard present in Waveshare 0.1.24 and T-Watch 1.1.25: System Apps 72f435fcee376ec62d17ece6180753385ea547d9, Apps/springboard.c plus its pinned PortableApps adapters. The native-height build is 146,576 bytes, SHA-256 3d1382056584b7f748f98ae08df317a39c7781e635069c5e4da7416ab80f332f. Rebuilding its recorded catalog-candidate-019c recipe reproduced raw hash f33ff27719ffd1faa1fb5f671579ada881aac29c9bd4c4673779798064470b17 and the exact deployed hash after relocation normalization and metadata compaction. It uses PORTABLE_WATCH_NATIVE_HEIGHT and the original capability-driven layout.

The launch route remains Home/default.elf request_launch("springboard.elf"), internal springboard.json, app_main, and the existing clock.elf return shim to fresh default.elf. No alternative SD launcher or hardcoded app catalog is selected. Restore its working 1.7.9 manifest and exact per-app provisioning row. Every other application and policy row, including Spectrum and Home, is preserved. Native Runtime, physical 410x502 display provider, boot animation, partition layout and SD contents are unchanged.

Both suite staging and the combined-build entrypoint now verify the pinned shared Springboard size/hash and reject the 0.1.25 substitute or any unknown rebuild. The restore script requires both exact release baseline hashes, verifies the freshly rebuilt artifact against the working image, and limits changed store files to Springboard ELF/manifest/policy plus cohort identity.

Validation: byte-identical source rebuild, selection rejection, ELF structural validation, full native store admission, deterministic SPIFFS round trip, unchanged native/other-app bytes and bank-state generation. Hardware execution remains unqualified pending the owner's test.
