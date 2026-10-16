# Waveshare provisioning source checkpoint

Work paused before native CI while the released0.1.52 sleep regression is investigated. This is incomplete source preparation, not a runnable release or firmware delivery. No binaries, feeds, release or catalog entry have been published.

Candidate0.1.53 is proposed over product main ff558f13c2b97c3d40a3c04d0b9f3d0103fc7038. The exact0.1.52 release was downloaded and its factory/store/release metadata hashes verified. All existing tracked source and historical recipes are unchanged. New candidate scripts are isolated.

## Verified inputs

- Common Home0.19.0 was independently built twice by the T-Watch integration task:625648 bytes; SHA256db23f172746ab32c0ba9c94d4c7a93d99be5f16247b6f267b48af8d7ca252d6f. The identical raw ELF is selected for both products.
- Exact released Settings remains157124 bytes, SHA256a7558b3bd2cd0c2a0edee95e4a8a69477a63772e8300e33e8e7332a2558f8d41. No replacement Settings or Springboard is selected.
- Newly selected installed-apps links179064 bytes. Checked loader-metadata-v4 compaction yields85660 bytes while preserving loaded sections, symbols, relocation targets and segments. Internal package adapter is3776 bytes.

## Unresolved capacity

Released0.1.52 contains128 files,62 ELFs and only6 completely free SPIFFS blocks. Adding the two providers yields132 files/64 ELFs. The first composition with raw Home, compacted new catalog and62 content-addressed SD mirrors has5,095,514 payload bytes and fails the unchanged0x550000 SPIFFS builder. Removing optional mirrors still fails at5,085,092 bytes. Unrelated JSON compaction saves only908 bytes. A copied-only retained-ELF probe saves6332 bytes excluding Settings/Home, insufficient; candidate retained ELFs were not changed. A source-equivalent -Oz/-flto experiment yields an82756-byte catalog, only2904 bytes below checked standard compaction, also insufficient by itself.

Do not substitute an older store or claim packing/native qualification. The existing partition geometry, complete retained inventory, required four-block provisioning reserve and exact Settings must remain explicit requirements. Source optimization or an independently authorized design is still needed.

## Remaining implementation and qualification

The package composer and mirror-policy helper are source drafts. build_provisioning_native.py is an unfinished draft: provisioning_qualification and provisioning_feed modules do not exist yet. No workflow is attached to this checkpoint. Complete host mutation controls, capacity resolution, retained platform graph count, exact native compilation/source closure, IQ/workspace placement, whole-store production admission and credential-free complete feed construction remain.

Factory self-admission must be distinguished from0.1.52→candidate preserving-transition admission. Home gains existing Wi-Fi namespace6. No preserving migration authority or update kit has been established. Preserve rejection controls; do not weaken the validator. Hardware first-start/profile acceptance and the reported sleep regression remain separate.

## Source Atlas coverage

Source set872eb870-e62e-495a-a7e5-ede6e2959342 pins product ff558f13, Watch bc72f4d and Runtime7110261. At23:34UTC, product was missing; Watch12/266 and Runtime12/3361 text records were indexed. No matching compiler configuration was indexed. Empty trace results do not establish absence. Exact checked-out source was inspected directly.
