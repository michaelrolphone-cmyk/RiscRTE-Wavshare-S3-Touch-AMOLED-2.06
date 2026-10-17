# Waveshare 0.1.55 paired candidate

Prepared, not published or physically qualified. The saved rollout requires a
recorded X4 catalog-update pass before Waveshare publication or hardware testing.
No successor firmware version is reserved; 0.1.56 belongs to provisioning work.

## Exact inputs

- Product producer: `1606e7070753c87a9ba6160933331dbcc0d50162`.
- Published firmware: `test-wifi-footer-0.1.55`, GitHub release `415527412`.
- Catalog source: `RiscRTE-Wavshare-S3-Touch-AMOLED-2.06:test-wifi-footer-0.1.55`, revision 1.
- Runtime: `f410c8592ecb37a520df3f29db8d88234dc7ddc9`.
- Frozen payload protocol: `908355b0509907c05a6dc47a1ccc8e078d6e23b0`, schema 1.0.0.
- Existing companion: `test-lora-media-0.1.17`, complete three-file inventory,
  138,235 bytes; its external executable is 136,960 bytes.

The producer verifies all 21 original GitHub asset hashes and lengths, catalog
factory identity, full-image native/store extraction, complete companion archive,
all source evidence, and the external ELF qualification lineage. It emits a
16,922,064-byte create ZIP and a 16,922,069-byte replace ZIP, each with the exact
16MiB full factory image and all three payload files. Each has a standalone
manifest, descriptor and reviewed-producer context. These are genuine nonfixture
schema 1.0.0 containers, not payload fragments.

## Product admission policy and trust boundary

`product-admission.json` belongs to product source. It distinguishes facts from
new narrow admission ceilings. The board descriptor itself says board ID
`waveshare-esp32-s3-touch-amoled-2.06`, revision `unspecified`; this is not an
invented physical PCB revision, a wildcard, or automatic board identification.
The operator must select the matching board. Runtime explicitly binds serial
namespace 12 to provider `sdmmc-fatfs`, instance 12. Namespace 2 is private ingress
and cannot fulfill the existing LoRa consumer.

The actual linked FatFs configuration and path validation support the selected
ASCII-insensitive naming mode, hierarchical paths, 511-byte path admission,
127-byte ASCII component admission, and the declared invalid characters and
trailing-dot/space rejection. The complete companion is ASCII and has no aliases.
The 136,960-byte per-file and 138,235-byte total ceilings are deliberately new,
release-specific admission caps, not the provider maximum or a claim of available
space. The 18,000,000-byte parser bound admits this full factory/container only.

The context records producer-reviewed source/consumer/install hashes and exact
container bytes. It is prepared for subsequent trusted catalog association, not
self-authorizing runtime data. Never derive installer trust from an arbitrary
manifest. After the X4 gate, upload the exact assets through the approved release
flow, read the resulting catalog source revision, rebind/rebuild if the source
identity or revisions change, then attach the reviewed descriptor/context with
the current revision. Catalog association is currently absent and remains absent.

## Execution and preservation

Order is firmware, payload, verify. Implemented method is `esptool-full-0x0`.
Factory flashing erases saved settings and internal data. External-media survival
is unknown and not relied on: transfer occurs after firmware. No whole-folder
replacement, formatting, recursive deletion, internal boot-bank write or implicit
upsert is performed. Create and replace are separate exact per-file variants.
Replace requires explicit selected-file approval, is in-place/non-atomic, and may
leave a partial selected file after interruption. No rollback is claimed.

Before use, establish an owner-trusted session and permissions, exact board and
target firmware, actual namespace admission and provider availability. Respect
the trusted write budget and any capacity information the supported flow already
provides, accounting for metadata/cluster overhead and reserves. RTEF1 has no
free-space query: do not add one or block on an unavailable query. The configured
admission cap is not a live fit guarantee. Known insufficient space is rejected;
a later NO_SPACE/short-write failure stops the transfer and follows the existing
partial-file reconciliation rules, without automatic retry. Keep Home awake and
exclude competing writers. STAT all parents/destinations, reject conflicts, and
recheck after flashing and immediately before each mutation. Stop on unavailable,
retained or I/O states; do not treat them as missing files. Require acknowledged
COMMIT/CRC plus full SHA256 readback of all files and actual consumer usability.

## Qualification and reproduction

Fresh normal and ASan/UBSan production-loader admission accepted the unchanged
LoRa ELF against .55's delivered 51-export native table. Eleven missing-import,
wrong-role, unsafe-state, four malformed/truncated negatives passed. Two actual
production removable-image fixtures used 4096-byte and 37-byte reads. All 17
required capability grants are present; optional radio.lora remains ungranted.
The delivered 62-internal-ELF normal/sanitized cohort proof is inherited only
after complete 128-file store digest verification. Xtensa execution, live provider
behavior and end-to-end application usability are not proved by these host tests.

Run using Python with jsonschema and pyelftools, cc and c++:

```sh
python scripts/qualify_catalog_pair_lora_055.py --base INPUT_ROOT --work PROOF \
  --helper-repo TWATCH_REPO --native-evidence PUBLIC_ASSETS/Waveshare-0.1.55-WiFi-Footer-Evidence.zip
python scripts/build_catalog_pair_055.py --assets PUBLIC_ASSETS \
  --companion Waveshare-LoRa-0.1.17-SD-card.zip --runtime RUNTIME_REPO \
  --schema FROZEN_SCHEMA_DIR --output CANDIDATE
python scripts/test_catalog_pair_055.py --candidate CANDIDATE --schema FROZEN_SCHEMA_DIR
python scripts/test_catalog_payload.py
python FROZEN_SCHEMA_DIR/test_validate.py
```

INPUT_ROOT contains the exact Runtime checkout, baseline qualification/store
files (including extracted store/), and lora/Waveshare-LoRa-0.1.17-SD-card/.
The pinned helper revision is 74f7491dc470b92dfa41fce41bf0c500f3714a94.
The producer writes no external state. Local results: two static-preflight passes,
30 real-candidate negative cases, 27 prior support tests, and 48 frozen-schema tests.
Hardware remains untested; publication/hardware sequencing remains unchanged.

## Exact publication transition

The saved catalog revision 1 is a preparation snapshot only. These manifests must
not be attached against a changed catalog revision. Publishing the new assets may
change the source revision/fingerprint, so publication is a separate gated step:

1. After the X4 pass, read the actual catalog release and payload-plan association
   revisions, and use the supported publication flow to stage the selected pair.
2. Capture the authoritative source snapshot that the catalog association will
   freeze. Reconcile new asset names, source fingerprint and exact source revision
   before producing the final manifests. Do not predict a revision number.
3. Update this producer's frozen catalog receipt only after reviewing that actual
   snapshot; regenerate both selected manifest and canonical container, then rerun
   full byte validation and rejection checks. Existing firmware/companion bytes and
   product trust pins must remain exact. If publishing changes the snapshot again,
   stop and reconcile with the supported association flow rather than attaching
   stale pins or fabricating an identity.
4. Read payload-plan again and attach the actual published descriptor and reviewed
   context with current expected association and release revisions. Re-read the
   association and verify the frozen source, digests and firmware asset before use.

The current producer explicitly requires catalog revision 1, upstream release
415527412, tag .55 and exact source/flash bytes; it rejects a changed receipt. This
prevents accidental reuse as a final-publication script. No claim is made that
the future catalog association or browser transfer has already been exercised.

Independent parent review at 2026-10-17 05:35 UTC reran both real positive
candidates and all 30 rejection cases successfully, and reviewed the source-derived
board and narrow ASCII-provider profile. This is scoped software review.
