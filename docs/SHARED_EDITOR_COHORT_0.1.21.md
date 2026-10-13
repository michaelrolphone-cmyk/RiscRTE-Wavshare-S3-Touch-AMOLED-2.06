# Shared watch editor cohort 0.1.21

Based on qualified Waveshare 0.1.20. This adds public Spectrum 0.5.5 shared text
input and modal policy, then public Waterfall 0.3.4 shared input and operation-scoped
AppData cleanup. The Utilities commits after the production pins are host-fixture
qualification changes only. Exact pins are in profiles/shared-editor-sources.json.

scripts/build_shared_editor_apps.py rebuilds both targets from those pins and the
preserved recipe inputs. Spectrum and RF outputs reproduce byte-for-byte after
normalization and metadata compaction. The alarm compatibility header is copied
unchanged from Utilities 80efb298 (identical to the selected RF header); the wrapper
matches the existing cumulative recipe. RF uses the current System PaperPresentation
contract, real Runtime app catalog, full fonts and native-height support.

scripts/compact_cohort_elf.py extends the shared v3 lossless compactor by removing
only nonallocated .comment and .xtensa.info compiler metadata. Its full segment,
loaded-section, symbol and relocation checks remain intact, and original ELFs are
retained as sidecars. Applying it consistently to all 60 cohort ELFs saves 37124
bytes, including previously retained .xt.lit/.xt.prop in the two update providers.
No loaded payload, interface, app, control, font, partition or reserve is removed.
The existing pinned 1 MiB-batched packer leaves 13 entirely free blocks / 196 pages.
Experimental compiler switches and SPIFFS GC packers were not selected.

The working vendor display, native Runtime, System and Productivity selections are
unchanged. Only Spectrum/RF application requirements gain ui.text-input@1 and the
matching instance-0 grant. Other ELF changes are proven nonloaded metadata removal.

Delivery remains held until 2026-10-13 23:30 UTC. No device operation is authorized
by this source checkpoint. Full initial images erase NVS/AppData if flashed.

The T-Watch handoff must consume identical application bytes including default.elf;
retain device-specific providers/configuration/grants. An old Watch receipt is not
proof of current delivered binary parity. The existing LoRa Messages versus Hardware
Test membership difference and unavailable-capability UI behavior remain explicit
parity work; do not manufacture LoRa or infrared hardware on Waveshare.
