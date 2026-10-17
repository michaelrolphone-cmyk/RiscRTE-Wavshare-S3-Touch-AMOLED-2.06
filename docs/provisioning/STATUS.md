# Waveshare provisioning source checkpoint

Historical checkpoint before the sleep-repair detour. Resumption measurements are recorded below. This is incomplete source preparation, not a runnable release or firmware delivery. No binaries, feeds, release or catalog entry have been published.

The historical, never-delivered draft candidate 0.1.53 was proposed over product main ff558f13c2b97c3d40a3c04d0b9f3d0103fc7038. The exact0.1.52 release was downloaded and its factory/store/release metadata hashes verified. All existing tracked source and historical recipes are unchanged. New candidate scripts are isolated.

## Verified inputs

- Common Home0.19.0 was independently built twice by the T-Watch integration task:625648 bytes; SHA256db23f172746ab32c0ba9c94d4c7a93d99be5f16247b6f267b48af8d7ca252d6f. That historical selection was later superseded by the smaller common Home below.
- Exact released Settings remains157124 bytes, SHA256a7558b3bd2cd0c2a0edee95e4a8a69477a63772e8300e33e8e7332a2558f8d41. No replacement Settings or Springboard is selected.
- Newly selected installed-apps links179064 bytes. Checked loader-metadata-v4 compaction yields85660 bytes while preserving loaded sections, symbols, relocation targets and segments. Internal package adapter is3776 bytes.

## Unresolved capacity

Released0.1.52 contains128 files,62 ELFs and only6 completely free SPIFFS blocks. Adding the two providers yields132 files/64 ELFs. The first composition with raw Home, compacted new catalog and62 content-addressed SD mirrors has5,095,514 payload bytes and fails the unchanged0x550000 SPIFFS builder. Removing optional mirrors still fails at5,085,092 bytes. Unrelated JSON compaction saves only908 bytes. A copied-only retained-ELF probe saves6332 bytes excluding Settings/Home, insufficient; candidate retained ELFs were not changed. A source-equivalent -Oz/-flto experiment yields an82756-byte catalog, only2904 bytes below checked standard compaction, also insufficient by itself.

Do not substitute an older store or claim packing/native qualification. The existing partition geometry, complete retained inventory, required four-block provisioning reserve and exact Settings must remain explicit requirements. Source optimization or an independently authorized design is still needed.

## Remaining implementation and qualification

The package composer and mirror-policy helper are source drafts. build_provisioning_native.py is an unfinished draft: provisioning_qualification and provisioning_feed modules do not exist yet. No workflow is attached to this checkpoint. Complete host mutation controls, capacity resolution, retained platform graph count, exact native compilation/source closure, IQ/workspace placement, whole-store production admission and credential-free complete feed construction remain.

Factory self-admission must be distinguished from0.1.52→candidate preserving-transition admission. Home gains existing Wi-Fi namespace6. No preserving migration authority or update kit has been established. Preserve rejection controls; do not weaken the validator. Hardware first-start/profile acceptance remain separate. The sleep repair has since been delivered in 0.1.54.

## Source Atlas coverage

Source set872eb870-e62e-495a-a7e5-ede6e2959342 pins product ff558f13, Watch bc72f4d and Runtime7110261. At23:34UTC, product was missing; Watch12/266 and Runtime12/3361 text records were indexed. No matching compiler configuration was indexed. Empty trace results do not establish absence. Exact checked-out source was inspected directly.

## Resume over delivered 0.1.54

Current main 42cb28ded2440f4386f3295138831a0d1cc68799 is incorporated without changing
its released recipes. Verified public 0.1.54 checksums file b5a3b12fa6df2c15d583b52183d912288a7d7a13236757dbfd8648473cff9c03
provides the new retained inventory. The qualified common Home 712127b109568431f1b34d4e947db46386945964
(610872 bytes, b5d8d7b545da737879a1d369160cd4c6eea4cee8876d09ce783cf00560f70231)
does not yet make the complete composition fit. See resumed-capacity-0.1.54.json:
132 files, 64 ELFs, 62 mirrors occupy 20,583 pages against 20,340 permitted pages with 4
free blocks. This is a 243-page deficit. The oversized scratch generator was used
only to count occupied pages, not to select a partition layout or create a product.

The original .53 preparation remains an unbuildable draft, not a new release identity.
Version .55 belongs to the independent Wi-Fi footer repair; a subsequent cumulative
baseline and identity must be coordinated. No native candidate or release was built.

Catalog linkage audit: allocated text 71,169 and rodata 3,662 bytes dominate after
loader-safe metadata compaction. Function/data sections plus linker garbage
collection grows the compact ELF from 85,660 to 86,548 bytes. Prior Oz/LTO probe 82,756
only saves 2,904 bytes. Neither is selected. All retained .54 ELFs remain exact.

Source Atlas set c53815c1-80c8-44b8-8a3e-cd69cd601a16 pins current product,
qualified Watch/Runtime and catalog System source. Its exact revisions currently
have no matching complete text/compiler coverage; empty trace results do not
establish absence. Local pinned-source review supplies syntax evidence only.

## 0.1.56 cumulative successor in progress

Version0.1.56/test-provisioning-0.1.56 is reserved after exact tag/catalog conflict
checks and coordination with the0.1.55 Wi-Fi repair owner. Final0.1.55 public
assets are the required baseline; older receipts above remain diagnostic history.

The separate shared Watch PR7 head2be519c2047b2323e4d399c1de19b0591dc87c59
is independently reviewed and passes all three GitHub workflows. Exact-source
run38992172220 artifact12084993852 independently reproduces the canonical Home
552616bytes, SHA2565797b757e228f2055f4fda3384659e91830f77ff03a636f9b3f605aeca8ace0d.
All11140 calendar-ring tuples and1632 full frames remain identical, including
ASan/UBSan. Common Home a/b and CI bytes match; hardware remains untested.

The updated complete internal core keeps all retained payloads. Only the original
optional external-only LoRa app remains on SD. The new installed catalog is85892
bytes and internal adapter3164, with exact loader-section/symbol/relocation proof
and retained original sidecars. Using the .54 diagnostic input,132 files/64ELFs
pack into the unchanged0x550000 store with95 free pages and6 whole free blocks.
The required4-block reserve passes. The bounded production catalog controller
parses the complete core and queues its exact image URL, size and digest.

The diagnostic source-bound host graph has22 platform tables; capacity32 suffices.
USB-PHY is selected and diagnostic-source is absent. Factory admission and the
namespace6-only control admit all64ELFs without hardware/storage calls. The
preserving transition rejects before ELF loading. Final .56 native CI must repeat
these checks over exact .55 inputs and verify linked DWARF, IQ and workspaces.

Product build, feed, admission and publication helpers now exist; their release
mutation tests and linked-layout tests pass locally. Product native compilation,
final cumulative packing and publication are pending. No hardware acceptance is
claimed. Previous release recipes and exact Settings remain unchanged.

## Final public baseline audit, 2026-10-17

The exact public 0.1.55 producer is 1606e7070753c87a9ba6160933331dbcc0d50162;
main merge 118073e5ae2d93b0c4d987b6da0e54475a4eba54 has the identical tree.
All 21 public assets match GitHub SHA-256 digests and the checksum manifest;
independent factory extraction confirms its firmware/store binding. The 128-file,
62-ELF baseline preserves the .54 sleep repairs and adds only the Wi-Fi footer repair.
The .56 recipe freezes every previous release recipe and preserves all 61 retained
non-Home ELFs, including Wi-Fi, Settings and Springboard.

Preflight with the exact .55 store plus selected .56 payloads packs 132 files and
64 ELFs into the unchanged store: 93 free pages, six whole free blocks, meeting
the four-block reserve. This receipt still uses .55 native firmware identity and
a placeholder product SHA; the exact .56 native composition is remeasured in CI.
Fourteen full payload tests, eight transport/publication mutation tests and three
linked-layout/compile-selection tests pass. The current mounted-SD repair is a
separate task and is not included in this source closure.

Merged Watch main 53282b569f5f2e2c7f55979c82b2eacad83dde30 CI 38993267445
artifact 12086840004 independently matches the immutable common Home 5797b757.
Exact ring source is available via Source Atlas GitHub fallback; the matching
revision has no complete text/compiler index, so no call-graph completeness is claimed.
