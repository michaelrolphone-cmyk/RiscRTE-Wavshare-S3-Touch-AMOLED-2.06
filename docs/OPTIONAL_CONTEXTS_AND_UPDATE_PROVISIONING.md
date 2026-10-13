# Canonical Contexts and update provisioning checkpoint

Runtime source a5c3e56448f32ee35d2a5f1aedd3e9d4e496426f ports the generic declaration repair from public RiscRTE 91cb1a0f4c0251b6d2eee941f6232b64d08163e0 relative to 95cd119. Only AppDeclarations.h, Runtime.cpp, InstallationRuntime.inc, and focused tests changed. Device profiles and layout are unchanged. The test runner uses Bash-3-compatible empty-array expansion; existing Clang host warning suppressions are supplied by the local compiler wrapper.

The corrected stage_contexts_catalog.py passes the older pinned helper its supported schema, then restores the canonical optional app.catalog@1 declaration. The helper previously rejected optional before restoration could run. Explicit app.catalog and ui.text-input boot grants remain. End-to-end staging passed.

The staged optional-contexts-0114/store differs from delivered 0.1.13 only in contexts.json. All 55 ELF bytes and boot.json are preserved, including the crown latch, panel sleep provider, Files, Waterfall, and shared Contexts ELF. The stage is not flashable: its old cohort record must be rebound during the next deliberate composition.

Local qualification: 258 focused checks normally and 258 under UBSan; normal and UBSan full-cohort admission each validated 55 ELFs, 178 cooperative yields, zero hardware calls and zero storage calls. Single-job esp32s3-16mb-waveshare-appdata target build passed. No hardware operation or behavior qualification occurred.

## Update provisioning

System worktree /tmp/waveshare-update-policy adds an explicit --product-policy-header selector restricted to --services-only. Default Watch/X4 branches and shared app builds are unchanged. The product-owned WaveshareUpdatePolicy.h selects only the exact Waveshare repository/product, rejects runtime-only updates, and has an empty feed URL. Four builder tests passed, as did both target provider ELF builds and the product service UBSan fixture.

The fixture tests actual unpublished 0.1.13 paired-payload metadata, product/repository/tag refusal, paired ABI/layout/capacity checks, Runtime downgrade refusal, USB-only image classification, and zero HTTP/bank activity when the feed is empty. The payload is firmware.bin + bootfs0.bin, 6,787,632 bytes, SHA-256 a0b8b0f0c47451cee71285770093ff307c1a04cde37fd52fc14f0415079f8301. It is neither published nor enabled.

Read-only repository checks found the exact public Waveshare repository, no release-index branch (404), and no releases. No publication was attempted at this checkpoint.

A concrete capacity probe adds only baseline ota_update.elf (112120 bytes), app_store.elf (112116), and the two new product providers (29680 + 29556) to the unchanged 0.1.13 store. The 283472-byte addition fails the same 0x510000-byte SPIFFS packer with File system is full, before including new manifests/grants. Baseline shared apps are used only to establish this capacity result; their native-height behavior is not qualified. No existing app was removed and no partition was resized.

Remaining work: qualified shared OTA/App Store app integration with a proven capacity solution; published product catalog/assets before enabling the feed; next composition identity/bank rebinding; physical confirmation of crown/sleep/display behavior. Delivered 0.1.13 remains untouched.
