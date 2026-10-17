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
the bounded mounted-card sleep repair will supply the successor Home/runtime
pins after shared-source qualification.

A version-specific `provisioning-index/0.1.57/native-packages-v1.json` feed keeps
the published 0.1.56 feed immutable. The installed-apps provider must be rebuilt
for this URL and included in the measured changed-file inventory.

## Qualification and delivery

The successor includes the bounded mounted-card sleep repair when its merged
component receipts and exact native product checks pass. Source pins remain
provisional until those receipts arrive. Full native builds run in GitHub CI.

Qualification must cover actual native provider selection/capacity, factory
self-admission, external-only image discovery and load, application preferences
and return to Home with all 21 moved ELFs absent internally, hidden navigation
glue, no-card recovery, complete SD inventory, and per-file create/replace plus
readback. Runtime catalog availability describes policy readiness, not live
media presence; no-card launch must recover safely rather than claiming the
external file is present.

Canonical catalog association will use the actual numeric GitHub release ID
and catalog revision after publication. Explicit create and replace variants
are separate; there is no automatic upsert. Installation order is firmware,
payload, then verification. Preserve unrelated SD files and existing app-data;
never replace a whole folder or format the card. The factory image erases
pre-flash internal settings/data, which is disclosed separately from post-
installation preference save/readback and external per-file preservation.

Software preparation and publication are authorized. Waveshare is the first
hardware firmware/storage test; hardware acceptance remains unmeasured here.
