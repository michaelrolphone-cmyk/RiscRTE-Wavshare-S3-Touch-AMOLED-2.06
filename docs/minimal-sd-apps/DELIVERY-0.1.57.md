# Waveshare 0.1.57 delivery

The software-qualified factory and associated SD payload are published in the
[firmware catalog](https://riscrte.com/#firmware). Physical acceptance is pending.

## Selected installation: existing LoRa card

For the owner's current **0.1.52 firmware and existing LoRa Messages SD card**, use
the catalog's **known-lora** plan. Its three historical LoRa targets require exact
previous byte counts and SHA-256 values before explicit replacement. The other
42 target files are created. Unrelated SD files and existing app-data are preserved.
Do not clear or format the card. A differing hash or unexpected existing target
stops preflight for explicit reconciliation; there is no automatic upsert.

The frozen generic RELEASE-NOTES.txt / TESTING.txt mention the clean `create`
variant. That variant is only for cards where all 45 target paths are absent.
It is **not the selected plan for the owner's existing LoRa card**. The separate
`replace` variant requires all 45 targets to exist. All three variants remain
immutable, independently verified artifacts.

The sequence is **firmware, payload, verification**. No intermediate 0.1.56
installation is required; 0.1.56 is the composition baseline. The bootstrap
context has a null pre-firmware identity. Only the new 0.1.57 firmware's namespace
12 is admitted for payload operations after flashing and reconnecting on Home.
Factory flashing at offset zero erases existing internal settings and data.
Back up first. No preserving update kit is supplied.

## Exact delivery

- Producer: `aa0664c2905abb264a6b07f35d027b4879562c68`
- Producer tree: `36c5af14daa7efb64274ca4bffd8f56545e81dcd`
- [PR 16](https://github.com/michaelrolphone-cmyk/RiscRTE-Wavshare-S3-Touch-AMOLED-2.06/pull/16)
  merged as `224731a81c63f24062dba6b8c87ee8a3745428fb`, identical tree.
- [Exact native and publisher CI](https://github.com/michaelrolphone-cmyk/RiscRTE-Wavshare-S3-Touch-AMOLED-2.06/actions/runs/39011908465/attempts/2)
  passed. Attempt 1's native build passed; its publisher hit an empty draft-list
  read immediately after creation. Attempt 2 resumed only the failed publisher
  using the identical successful native artifact.
- [Merged provider CI](https://github.com/michaelrolphone-cmyk/RiscRTE-Wavshare-S3-Touch-AMOLED-2.06/actions/runs/39013210794)
  passed.
- [Immutable release](https://github.com/michaelrolphone-cmyk/RiscRTE-Wavshare-S3-Touch-AMOLED-2.06/releases/tag/test-sd-apps-0.1.57):
  GitHub ID `415643536`, 35 assets.
- SHA256SUMS: `0a5dfa1c0cd287a71354631a062075bc87b53384064a4ff803ce2ae45fb9fc65`
- Factory: 16,777,216 bytes,
  `4b040de94b3d25c5f383a29f6bff56fb6e39a1cca75ababd968c5405543a8c5c`
- Store: 5,570,560 bytes,
  `6443ce09c81b3f8b5fb1dcd6e40b7fab3ff81cdae98241fb0a8c93e362e97d13`
- Known-LoRa container: 19,923,653 bytes,
  `9b579e8c2dffff503f8ed35594be1a03a4d8ca891aa9b035bb3d535047f24b5f`
- Known-LoRa manifest: 25,781 bytes,
  `d609cd19b9b7b61a639822724f5c0a1a0046eb06a7ceda420378d1103104af8e`
- Catalog content revision 1 and payload-plan revision 1: approved, not stale.
  Factory verification returned available, checksum verified, and orchestrated
  flash available. These are software/publication checks, not device acceptance.

## Qualification and limits

Five apps remain internal: Home, Springboard, Wi-Fi, Settings and the hidden
return-to-Home shim. All 38 providers remain internal. Twenty-one retained app
ELFs move byte-identically to SD alongside LoRa Messages: 45 files, 22 external
apps, 3,113,484 bytes. Internal store: 111 files, 43 ELFs, 791 whole free 4 KiB
blocks. Partition sizes are unchanged.

The exact native graph has 22 platform tables with 32 linked slots. The IQ bank
is 0x3fcb0000–0x3fcc0000 (65,536 bytes); the linked heap/static end is 0x3fcafe00,
leaving a 512-byte gap. IRAM ends at 0x40391700; IQ alias begins at 0x403a0000.
Boot-view and serial workspaces occupy 288 and 2,792 bytes in .ext_ram.bss;
package workspace requires 15,208 internal bytes. This is linked-layout proof,
not a measurement of physical heap availability.

Independent public audit verified all 35 asset digests, extracted firmware/store
from the factory, reconstructed retained/moved payloads and all three canonical
containers byte-identically, and checked the versioned core feed. Normal and
ASan/UBSan Runtime navigation/serial qualification passed 16 cases; eight
historical Springboard client cases passed. Production ELF admission covers all
43 internal and 22 external ELFs. Canonical validation passed three positive
plans and rejected 45 mutations. No target instructions or physical display,
radio, card durability, sleep/wake or install timing are claimed by host tests.

Receipts: [public-byte audit](public-byte-audit-0.1.57.json) and
[catalog qualification](catalog-qualification-0.1.57.json). Complete native,
source custody and fixture evidence is in the immutable release Evidence ZIP.

## Hardware test procedure

1. Back up internal settings/data and note unrelated SD files/app-data to check.
   Start from 0.1.52 with the existing LoRa card inserted. Select catalog 0.1.57.
2. Confirm the guarded known-LoRa plan and factory erasure disclosure. Follow
   firmware-first flashing. Wake the new 0.1.57 on Home and reconnect when asked.
3. Complete 3 guarded replacements, 42 creates and full file readback. Do not
   proceed after a previous-hash mismatch, unexpected collision or uncertain
   transfer result. Preserve the card for diagnosis.
4. Check unrelated files and existing app-data remain. Open Calculator, Audio
   Spectrum/Waterfall and LoRa Messages from Springboard; return to Home.
   The hidden clock navigation shim must not appear as a launcher item.
5. Save a preference, return Home, reopen and reboot to verify readback. This
   checks post-install persistence, not preservation of erased internal data.
6. Check Home, Springboard, Wi-Fi and Settings without a card. External entries
   may remain visible; failed launches should recover Home. Reinsert the card
   and verify external app launches recover.
7. With the card mounted and no active transfer, test normal sleep, crown wake,
   alarm wake and repeated sleep/wake. Report firmware, steps, expected/actual
   behavior and available logs for failures.
