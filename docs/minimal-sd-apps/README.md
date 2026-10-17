# Waveshare 0.1.57: essential internal apps and complete SD payload

This source checkpoint reserves `0.1.57` / `test-sd-apps-0.1.57` after checking
GitHub tags/releases and the maintained catalog, including archived records.
It starts from cumulative main `23d40324d600f7bdebb4ed4cd2a10bcf3b4fef38` and
independently audited public 0.1.56 bytes. Earlier release recipes remain intact.

## Accepted placement

Keep Home, Springboard, Wi-Fi, Settings and the 1,232-byte return-to-Home shim
internally. The shim is navigation glue and will be explicitly hidden from the
application catalog. Move the other 21 internal application ELFs to their exact
`Apps/<app-id>/<file_name>` paths on generic storage volume instance 12, with no
internal fallback. Preserve the existing external LoRa Messages payload and
include every required packaged asset. Small boot-owned manifests and grants
retain the existing application identities and data mappings.

Retain all 38 providers internally. The five essential application manifests
have a 27-provider dependency closure, but exact Runtime image admission still
inspects all configured driver images. This change does not optimize provider
placement. `baseline-0.1.56.json` records the full 132-file baseline and the
application/provider closure. Its Home hash is historical baseline evidence;
the bounded mounted-card sleep repair supplies the exact successor Home/Runtime
pins now recorded in source-pins.json.

A version-specific `provisioning-index/0.1.57/native-packages-v1.json` feed keeps
the published 0.1.56 feed immutable. The installed-apps provider must be rebuilt
for this URL and included in the measured changed-file inventory.

## Qualification and delivery

The successor includes the bounded mounted-card sleep repair when its merged
component receipts and exact native product checks pass. Component sources are
qualified and merged; the exact product build remains pending. Full native
builds run in GitHub CI.

Qualification must cover actual native provider selection/capacity, factory
self-admission, external-only image discovery and load, application preferences
and return to Home with all 21 moved ELFs absent internally, hidden navigation
glue, no-card recovery, complete SD inventory, and per-file create/replace plus
readback. Runtime catalog availability describes policy readiness, not live
media presence; no-card launch must recover safely rather than claiming the
external file is present.

Canonical catalog association will use the actual numeric GitHub release ID
and catalog revision after publication. Explicit create, replace and known-LoRa mixed variants
are separate; there is no automatic upsert. Installation order is firmware,
payload, then verification. Preserve unrelated SD files and existing app-data;
never replace a whole folder or format the card. The factory image erases
pre-flash internal settings/data, which is disclosed separately from post-
installation preference save/readback and external per-file preservation.

Software preparation and publication are authorized. Waveshare is the first
hardware firmware/storage test; hardware acceptance remains unmeasured here.

## Measured preparation checkpoint

The exact mounted-card Home is 552,856 bytes, SHA256
`2488ba37935dfa1601904b6c62802293fabcaab8000c203377e70707bf6685cf`.
The async SD provider 0.2.2 is 47,004 bytes; the versioned-feed catalog is 85,896
bytes. The composed internal store has 111 files/43 ELFs and 791 empty 4 KiB
blocks, without changing partitions. The full external payload has 45 files,
22 ELFs, 3,113,484 total bytes and a 288,112-byte largest file. These are measured
package bounds; they do not establish live SD capacity.

The old LoRa boot manifest remains 0.1.16; its preserved public SD manifest is
0.1.17. Their only differing field is version. All other 21 moved ELF/manifest
pairs are exact public 0.1.56 bytes. No baseline non-ELF/non-manifest packaged
asset is discarded. Existing user documents/models/app-data are not replaced
by this application payload.

Normal and ASan/UBSan host diagnostics accept all 43 internal ELFs, 22 platforms
and the placement transition; an unauthorized namespace 6 control is rejected
before ELF admission. All 22 external ELFs pass production structure/admission
and owned-snapshot tests. Those preparation runs deliberately used 0.1.56 native
export evidence, so they do not qualify the new native firmware. The final CI
repeats them against its own freshly linked 0.1.57 ELF and records the distinction.

The versioned 111-file core feed passes the production controller's bounded
parse, native-identity and exact image/digest queue tests. Required core packages
stay internal; the external application payload is installed by the canonical
catalog plan. These source/model checks do not establish physical application
execution, SD timing, USB transfer or sleep/wake acceptance.

## Explicit per-file installation plans

The canonical release offers three static plans: create (all 45 target paths absent), replace (all 45 already present), and known-lora (three immutable test-lora-media-0.1.17 paths must match previous byte counts and SHA256; other 42 target paths absent). The mixed plan replaces only those three LoRa files and creates the rest. Every plan preserves unrelated SD contents and existing app-data. No plan selects create versus replace automatically. Other mixtures require a verified inventory-specific plan; do not clear a card or application data to make a plan fit. Select the catalog association only after the card state or verified preflight identifies the applicable plan.
