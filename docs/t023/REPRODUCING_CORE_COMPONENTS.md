# Reproduce T023 preserving components

`profiles/t023-reproduction.json` is the portable recipe: exact public component
pins, complete released baseline file inventory and factory hash, full Home and
Springboard feature flags, expected component hashes, and parameterized build and
composition commands. It uses separate System source pins for the provisioning
provider and the already-qualified RGB client. No whole-tree merge is required.

Use the exact pinned GCC 8.4.0 toolchain and Python with pyelftools. Supply absolute
paths for each placeholder. Clone/check out each public source pin before running
its command. The Runtime SDK's used header hashes are recorded separately from
the final product-native source. Verify them before rebuilding providers; the
original build receipt truthfully records local Runtime 100540a2. Never relabel an
existing artifact as built from another commit.

Verify the downloaded factory asset SHA-256 and every extracted baseline filename
and hash against the recipe before composition. The entire baseline is retained.
The factory asset is an input for reconstruction, not an instruction to flash or
erase a device. All build outputs, original-ELF sidecars and logs belong outside
source checkouts and outside the composed store.

Run the recipe commands in this order:

1. `home`, using the exact Shared/System/Utilities pins and selected preferences.
2. `springboard`, which runs this product's `scripts/build_t023_springboard.py`.
   It imports the pinned RGB compiler recipe, materializes only the pinned bridge
   sources, retains every original feature define, and adds package discovery.
   It preserves the complete baseline manifest and appends only optional
   installed-apps and storage-volume declarations. The same client tolerates a
   missing SD grant on internal-only Watch.
3. `catalog` and `internal`, with `NATIVE_APP_CC` explicitly set to the recipe's
   compiler path. Catalog product identity must exactly equal the baseline cohort.
4. `compose`, only after obtaining the exact native firmware and a verified
   native-selected-provider manifest list. The recorded selection is empty
   because the examined native configs had no policy-header override and their
   selector returned an empty set. Reverify the exact final native inputs; do not
   infer that hardware platform capabilities are selected native driver images.

The Springboard builder requires a new output directory and checks the exact RGB
source commit, compiler binary, baseline manifest, source recipe, ABI imports and
exports, Runtime ELF validation, and expected final ELF bytes. It never changes
source or downloads inputs. Its generated build receipt contains the exact command.

Wave uses atomic Home and atomic Springboard quick preferences, matching the
verified 0.1.39 baseline. NVS-only replacements would remove an existing feature.
The explicit `--compact-new-providers --compact-rebuilt-apps` options apply the
existing v4 checked compactor only to the two newly added providers and the
freshly rebuilt Home/Springboard replacement copies. No untouched baseline file
is compacted. The raw component hashes stay separately recorded from the final
compacted hashes in the recipe. Full originals and semantic-equivalence evidence
remain outside the store; image-source hashes are derived after compaction.
The rebuilt-app step recovers 94,632 bytes (Home 232; Springboard 94,400) without
changing any retained loader semantics, features, declarations or partitions.
The existing SD-only LoRa policy remains intact. Final native builds must stage
the exact product VendorDisplay.cpp and pinned vendor library; the first native
CI artifact omitted that backend and cannot qualify the product.

Final feed profiles explicitly use `time.cloudflare.com` for SNTP, as selected
by the user. The recipe makes no implicit time-source or hosting choice.

Before release, publish this recipe checkpoint and use that full public commit as
`cohort.source_revision`. Regenerate the exact migration header from the actual
baseline/candidate snapshots, include corrected native driver digests and all
product-native inputs, rebuild native firmware, and regenerate its cohort binding.
Complete packed-store, graph, native pairing, preserving-update and migration
admission must pass. Current component reproduction is not final native admission,
a release, or hardware qualification.

Tests: `python scripts/test_t023_reproduction.py` and
`python scripts/test_t023_boot_profiles.py`. Set `T023_SPRINGBOARD_REPLAY` and
`T023_HOME_REPLAY` to separately built component directories to check the exact
ELF and generated-manifest hashes recorded in the recipe.

Set `T023_COMPOSED_STORE` to a separately composed store to verify its exact
compacted app/provider hashes, complete baseline file retention and unchanged
untouched file bytes against the recipe. Native binding still requires final
qualified native inputs; this optional check does not substitute for admission.
