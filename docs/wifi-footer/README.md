# Waveshare 0.1.55: Wi-Fi footer touch repair

The native-height Wi-Fi view draws Prev, Select and Next using the Watch layout transform. The retained controller instead interprets those footer taps in legacy centered 240-pixel coordinates. At 410×502, visible footer taps were ignored; Back and list-row handling followed other paths. System Apps PR118 corrects the footer transform and tests scan start/cancel, navigation, gaps and Back at supported square and tall sizes.

## Exact package and product scope

- Baseline: public Waveshare 0.1.54, source `55ba8842a28018bf2ae539f51c6ec2b2622e8a80`.
- Runtime stays `f410c8592ecb37a520df3f29db8d88234dc7ddc9`, preserving the .54 Deep -3 repair.
- The retained Wi-Fi recipe is reconstructed from its four exact source revisions and verified input hashes. GCC 8.4 first reproduces the released 169460-byte ELF, SHA256 `7bb9d98ace7cb783e6f85368c0dfd29360b96a635766c6f3f637b6901ae0d6c8`.
- Only `Apps/wifi_settings_portable.inc` is replaced with the correction from merged System Apps `297c38619a867f6200cc2f605b6193e4394bdfa2`; the embedded version becomes 1.1.34. Two independent builds must produce the same 169460-byte ELF, SHA256 `25a5b8c1f36f4c9ea4edf7a6bcae5b890264a646bbbd2bca37e8c153c5233247`, with unchanged imports and exports.
- The previous package manifest was 1.1.33 while its historical compile command embedded 1.1.30. The new ELF and manifest both identify 1.1.34. Manifest grants, requirements, identity and other fields are preserved.
- Exactly three of 128 store files change: `wifi_settings.elf`, `wifi_settings.json`, and `cohort.json`. All 125 other files, including 61 ELF files, remain byte-identical. Canonical Home and the power provider are independently rebuilt to their retained digests.

The source pins retain the canonical Home's original System dependency separately from the Wi-Fi repair source. A fresh native build binds firmware, source, cohort and store to one product revision. Admission checks cover all 62 ELF files normally and under sanitizers; deterministic store extraction, factory binding, IQ memory guards and the existing 496-case preservation model remain required.

## Qualification and delivery

`wifi-footer-native.yml` runs the package/release mutation controls, focused Wi-Fi touch tests, retained .54 sleep/serial/power regressions, source-bound native build and complete release verification. Source publication initially has `publication_enabled=false`; enabling it requires the qualified source and a complete immutable release bundle.

The standalone Wi-Fi ELF, manifest and source/build receipt are included in the release assets and evidence archive. The factory image erases internal data and settings. The preservation model does not change that factory warning. Hardware behavior remains untested until reported against this candidate. The concrete regression is ignored native-height footer input; broader freeze reports may have additional causes.

Hardware checks: open Wi-Fi, repeatedly use Prev/Next, select Scan, cancel, return with Back and reopen. Record responsiveness and any error. Repeat the .54 no-card/no-host Battery→Home→Hybrid sleep scenario and the existing alarm/wake checks described in the generated TESTING.txt.
