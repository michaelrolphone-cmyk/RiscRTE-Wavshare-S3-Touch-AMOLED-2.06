# T023 automatic core bridge: source-only composition

## Status and inputs

The opt-in composition is source-tested; no new product binary, public feed,
release, device execution, or complete native/store admission is claimed here.
The combined Runtime and System source pins remain **pending tested commits**.
Historical checkpoint/admission JSON and `t023-migration-policy.h` describe their
original exact sources; they do not qualify a newly composed bridge automatically.

Minimum reproducible inputs:

1. The complete verified Wave 0.1.39, cohort source 14470ddf68b5fd892d467b12e9b94abcd78ea198 baseline store,
   including every manifest, ELF, data file, board/boot/cohort policy and metadata.
2. Exact newly built Home (`default.elf`, `default.json`) and Springboard
   (`springboard.elf`, `springboard.json`) directories. Product declarations for
   both apps are retained. Existing grants/private namespaces are preserved.
3. System installed-apps output built from the tested combined System/Runtime
   checkpoints with all of `--native-feed --boot-profiles --internal-packages`,
   `--feed-product waveshare-s3-touch-amoled-206`, and an explicit verified product feed URL.
   `build.json` must describe those flags/product and the exact `driver.elf` hash.
   The request ABI is System's `lib/PortableApps/include/RiscProvisionRequestV1.h`.
4. System `scripts/build_internal_packages.py` output (`driver.elf`,
   `manifest.json`), built against the same exact Runtime SDK.
5. Native `firmware.bin` from the exact product profile and selected source-bound
   overlays; a candidate product version and a full 40-character source revision.
   An explicit `--runtime-version` is required in bridge mode and must match the
   firmware binary's `RISC_RUNTIME_VERSION:` marker. The combined native version
   for this candidate is `0.3.4`; the baseline version must not be inherited.
6. A JSON list of exact native-selected provider manifest paths. Supply `[]`
   explicitly if the selected native policy has no provider images. This list
   must match the native build, not a guessed list of hardware providers.

Build service inputs with System's existing builders, for example:

```sh
python "$SYSTEM/scripts/build_installed_apps.py" \
  --runtime-repo "$RUNTIME" --output-dir "$CATALOG" \
  --internal-packages --native-feed --boot-profiles \
  --feed-product waveshare-s3-touch-amoled-206 --feed-url "$VERIFIED_PRODUCT_FEED_URL"
python "$SYSTEM/scripts/build_internal_packages.py" \
  --runtime-repo "$RUNTIME" --output-dir "$INTERNAL"
```

Stage the product's native config/header in the matching Runtime checkout and
select `env:waveshare-t023-boot-profiles` with PlatformIO. It inherits the existing
T023 profile and only adds `RISC_NATIVE_PROVISION_REQUEST=1`. The legacy
`env:waveshare-t023` remains available without that flag. Runtime must include the
request queue, complete 160-file inventory, and boot/default app internal fallback
changes. Do not substitute a different product's native profile or partitions.

```sh
python scripts/compose_provisioning.py \
  --baseline "$BASELINE_STORE" --home "$HOME_BUILD" \
  --springboard "$SPRINGBOARD_BUILD" --catalog "$CATALOG" \
  --internal "$INTERNAL" --firmware "$FIRMWARE_BIN" \
  --version "$CANDIDATE_VERSION" --source-revision "$PRODUCT_SOURCE_SHA" \
  --runtime-version "0.3.4" \
  --output "$NEW_STORE" --boot-profiles \
  --native-provider-manifests "$NATIVE_MANIFEST_LIST_JSON" \
  --composition-report "$EVIDENCE_DIR/composition.json"
```

`NEW_STORE` must not exist. The report must be outside the store. The composer
preserves the full file inventory, hashes every file, verifies unchanged bytes
outside the six intentional boot/cohort/Home/Springboard replacements, and
rejects stores exceeding 160 files. This limit does not establish SPIFFS fit;
pack the entire final store and perform exact native/store admission separately.

## Image policy

All boot-owned internal app images, including Home, and eligible provider
images receive a relative `Apps/<manifest-id>/image-<sha256>.elf` or
`Drivers/<manifest-id>/image-<sha256>.elf` source with volume12 and
`internal_fallback: true`. Digests are computed from the final internal ELF bytes.
Run compaction/relinking before composition, never after it. This does not copy
assets to SD or publish a feed. The public feed builder verifies and publishes
those exact assets only after independent admission.

Every storage.volume provider, every explicitly selected native provider, and
their transitive software dependency closure stay internal. The software graph
and added image-source edges must remain cycle-free. USB MSC retains its explicit
SD12 binding. No existing grant or namespace is broadened for mirroring.

Existing external-only features are preserved without fabrication. The verified
0.1.39 baseline has an SD-only lora_messages policy and no internal ELF. That row
remains unchanged and is reported separately, outside automatic core mirrors.
Without the existing external file this feature remains unavailable, as before.
The baseline-only policy check finds 61 eligible unique mirrors and 128 files;
this is not the final composed artifact inventory or a new admission result.

The task tree initially lacked the current Wave native overlay; it is now
recovered from `fix/t023-wave-bindings` at
`c4df70f382f5a78fc61ebb45a0e7c1b0462d8354`. The existing
T023 config extends `env:waveshare-t051` and needs its exact
`expanded-candidate.ini`, `waveshare-settings-profile.h`, `src/VendorDisplay.cpp`
and other source-bound inputs. The product's older checked-in expanded profile
is not a replacement. The matching native branch is `fix/t023-wave-bindings`
at c4df70f before the pending combined Runtime changes.

## Optional lossless provider compaction

Default composition copies both new provider ELFs byte-for-byte. If the packed
store is too tight, explicitly add these arguments to the bridge command:

```sh
  --compact-new-providers \
  --compiler "$XTENSA_TOOLCHAIN/bin/xtensa-esp32s3-elf-gcc" \
  --debug-sidecar-dir "$EVIDENCE_DIR/original-provider-elfs" \
  --composition-report "$EVIDENCE_DIR/composition.json"
```

With `--compact-new-providers`, only newly added `installed-apps/driver.elf` and
`pkg-internal/driver.elf` are eligible. No untouched baseline app, driver, data
file or manifest is compacted or removed.
The original catalog build receipt is validated before copying; the checked
compaction runs before the final image_source digests and inventory are computed.
The caller must provide the actual compiler path and matching adjacent objcopy.
Python must have pyelftools available for this explicit mode.

This uses the product's existing `scripts/compact_cohort_elf.py` unchanged. Its checks
compare all retained header/segment, section-order, loaded-section, global/weak
symbol, referenced-local-symbol and relocation semantics. The composition report
retains the complete compactor receipt plus every retained semantic field (raw
section/segment bytes represented by length and SHA-256), component equality
results, before/after semantic hashes, checker-source hash and tool details.

The full original ELFs remain under the separate debug-sidecar directory, using
the same two relative paths. Existing sidecars are never overwritten. Input trees,
store paths, sidecar/report aliases and nested escaping symlinks are rejected
before composition. The two source build outputs remain unchanged. Actual final
store packing and complete native/store admission still decide whether this fits;
compaction does not change partitions or claim admission by itself.

Wave also supports the separate opt-in `--compact-rebuilt-apps`. It selects only
the newly built replacement `default.elf` and `springboard.elf` copied from the
explicit Home and Springboard build directories. Their original `build.json`
receipts must match each ELF's hash and byte count before any store is copied.
The build directories must be separate from the released baseline. It requires
the same explicit compiler, external sidecar directory and composition report,
and can be combined with provider compaction. Neither flag enables the other.

The existing v4 checker runs on the replacement copies before deriving boot
image-source hashes. Full original replacement ELFs, unchanged source build
outputs, receipt hashes and complete semantic-equivalence proofs are retained.
The report separates `rebuilt_app_compaction` from `provider_compaction`.
Default composition does not compact either class. This is a metadata-only
capacity option, never a feature-removal or baseline-file-stripping mechanism.

## Qualification before use

Regenerate and qualify any exact native migration policy against the actual
source/target snapshots. The historical embedded policy cannot authorize new
source revisions or changed app policy JSON. Old native firmware cannot be
assumed to accept the bridge directly; use only a separately qualified preserving
native-first path. Do not reset saved data, repartition, format, or claim direct
OTA migration without evidence.

Run `python scripts/test_t023_boot_profiles.py`. These tests use explicitly
synthetic source fixtures to check complete 160-file preservation, unchanged
manifests/data, grants/namespaces, content addressing, default-app fallback,
transitive storage/native closure, cycle rejection, opt-in behavior, rejected
mismatched catalog receipts, missing images, and internal-only operation.
They are not substitutes for real ELF/native admission or hardware checks.
