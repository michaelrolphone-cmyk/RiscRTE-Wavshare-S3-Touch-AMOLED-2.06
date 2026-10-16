# Existing firmware-associated payload preparation

This support-only audit pairs the exact delivered Wave `test-shared-default-0.1.52`
firmware with the existing `test-lora-media-0.1.17` companion. It changes no product
profile, Runtime pin, executable, internal boot file or application placement.
It does not publish a release, reserve a product version or operate hardware.

## Complete inventory and actual consumers

The independently downloaded factory image contains the exact released 128-file
internal store (62 ELFs, 66 JSON files, 5,011,431 bytes). That store remains
firmware-owned. Its `boot.json` explicitly selects `lora_messages.json` with
`image_source.volume_instance = 12` and path
`Apps/lora_messages/lora_messages.elf`. This is the sole external executable.
The default and all storage-provider dependencies remain internal.

The complete separately published companion contains exactly:

| Namespace-relative destination | Bytes | Role |
|---|---:|---|
| `/Apps/lora_messages/lora_messages.elf` | 136960 | Existing Runtime removable app consumer |
| `/Apps/lora_messages/manifest.json` | 932 | Distribution metadata, same admission fields as internal manifest; version 0.1.17 |
| `/suite-card.json` | 343 | Distribution index and ELF digest |

Total: **3 files, 138,235 bytes**. Every exact digest and original asset/source
identity is in `baseline.json`. The external manifest and card index do not
grant authority or install an app. The internal 0.1.16 manifest and boot grants
remain authoritative. No additional external asset is referenced by the existing
companion. Missing media follows the existing unavailable-app path; there is no
internal application fallback. Optional `radio.lora` remains unavailable on this
product when no compatible hardware/provider is present.

Runtime `9f8d67029181f6cd064e247aa949a295854fc494` `src/main.cpp` explicitly binds
the separate serial client to the selected `sdmmc-fatfs` provider instance12.
`NativeSerialStorage.cpp` admits that client as namespace12. This is source-proved
binding, not routing inferred from its label. Private namespace2 is isolated
`/appdata/.serial-files`; it does not satisfy this application destination.
The active boot bank is not a writable serial destination.

## Reproducible support

`python scripts/test_catalog_payload.py` runs focused negative and inventory tests.
The complete audit verifies all baseline asset bytes, factory/store extraction,
all128 internal file hashes, every external image-source declaration, all three
companion files, companion provenance and manifest equivalence. It reads exact
Git objects, independent of the checkout's current branch:

```sh
python scripts/audit_catalog_payload.py \
  --assets /path/to/firmware-assets --companion-assets /path/to/lora-assets \
  --source product=/path/to/product --source runtime=/path/to/runtime \
  --source schema=/path/to/runtime --source watch=/path/to/watch \
  --source image_helper=/path/to/twatch --download --output /path/to/audit.json
```

The repositories must contain the immutable objects listed in `baseline.json`.
`--download` fetches only exact public release assets and rejects byte changes.
The output includes a factual audit plus canonical `payload-create.json` and
`payload-replace.json` **payload fragments**, matching schema1.0.0's payload shape.
They are not complete installable manifests, containers or trusted catalog
contexts. Create and replace are separate, explicit per-file selections; no
implicit upsert, folder replacement, deletion or formatting is introduced.

The pinned manifest schema is at Runtime
`908355b0509907c05a6dc47a1ccc8e078d6e23b0/docs/catalog-payload/1.0.0`.
No schema modification or synthetic sentinel is used.

## Remaining catalog/builder inputs and qualification

The current release catalog record (revision1, checked2026-10-16) explicitly
admits profile `waveshare`, full factory asset
`Waveshare-0.1.52-Shared-Default-factory-erases-data-0x0.bin`, offset0, size16777216.
It does not expose a generic `method_id`, accepted hardware-revision list or a
trusted namespace-capability/budget profile. Profile `waveshare` revision1 also
lacks those generic fields. The website builder must supply those exact existing
installer/profile facts and bind the eventual manifest/container digests to the
selected immutable catalog revision. This source does not invent such IDs or
self-authorize a context. The expected case-insensitive ASCII naming requirement
in the payload fragment must be checked against that trusted provider profile.

Select firmware → payload → verify for this factory pairing. Factory flashing
erases saved settings and internal data. External-volume preservation is not
claimed; transfer after flashing avoids depending on it. Re-establish the actual
target firmware/provider before transfer and require complete acknowledged
COMMIT/CRC and full SHA256 readback of all files afterward. Keep Home awake and
prevent competing consumers/writers during transfer. Replacing an explicitly
selected file is destructive and non-atomic; interruption may leave it partial.
Unrelated siblings remain outside the transfer inventory. Missing/retained/I/O
provider states are not file absence and must not trigger fallback/retry.

Exact external-ELF admission against the delivered native export table, full
installer integration and physical end-to-end usability remain separate evidence
requirements. Product publication and hardware qualification remain behind the
recorded X4 catalog-update pass. A source audit or CI pass does not satisfy them.
