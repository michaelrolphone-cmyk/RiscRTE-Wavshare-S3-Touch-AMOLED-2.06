# Qualified full-profile scene replacement

The mixed 1aaf53e scene / f4b30f8 text provider pair is not deliverable: the shared
owner reproduced rejection of ordinary Contexts editing because the older scene
rejects POLICY_INPUT_CONTINUITY. The corrected composition replaces only the
scene ELF and its manifest, using System f4b30f8ebcc6d8cb905c8e90c91b1691acbe8165
and that revision's matching SDK. The four-dependency overlay remains without
input.navigation; scene version becomes 0.4.6. Contexts and text ELF bytes, other
providers, app permissions, fonts and full-profile compiler flags are preserved.

`scripts/stage_qualified_scene.py` implements this local replacement into a new
store and rejects unexpected binary sizes or hashes. It preserves the raw ELF
and verifies loader-metadata-v3 parity before installing the compacted component.

- Raw: 480824 bytes, SHA256 4e9ac1dd5424c6e487142c07217f03c30933452f16577526536bfefc448ab021.
- Compacted: 310220 bytes, SHA256 017039a424e0482cf35c062a5b883af621bda0457e8bb9ff321fe63640e54fa1.
- Component increase: 101444 bytes over the already-compacted old scene.

The generated fonts/telemetry.inc must be 272953 bytes with SHA256
2d7501e42d6223ebbc191817715431182c435fea944a1a02166a0748a577eaf1.
It was materialized from Library libfile_4ba4bac29dbc8191b1efee4ac464b45f,
file_000000005ff08230b630fb048f526a55 version 0, and verified on the consuming Mac.
The producer uses Linux Pillow12.3.0/FreeType2.14.3/libraqm0.10.5. macOS with the
same Pillow/FreeType but no libraqm generates a different font hash
ac93205740c41dc2ce22489abeafcad921b7cba1bf8db2ec6d49ea7d3265425f and a different
ELF. That alternative is preserved separately and rejected by the build gate.
No rendering source or fonts were simplified to obtain a matching artifact.

Normal and UBSan real Runtime admission pass for all 50 ELFs (21 apps and 29
providers), with zero hardware/storage calls. These are local software checks.
The shared owner separately reports 808 actual provider/app cases and 20
no-navigation sanitizer cases on the corrected pair at both watch geometries.

## Whole-image capacity boundary

The exact store payload is 3950310 bytes in 102 files. Runtime append accounting
charges 16661 pages against a 19380-page budget in each 0x510000-byte bootfs slot.
Native firmware is 1479120 bytes within each 0x260000-byte application bank.
Partition sizes remain unchanged, including the independent 0x80000 app-data.

However, actual packing with the local macOS PlatformIO tool-mkspiffs 2.230.0
Arduino ESP32 binary fails with SPIFFS_write(-10001), filesystem full, while
adding timecard.elf. Its SHA256 is
c6705f8dfc0b0a51a91ed35e1f8a83a312395a36ba872ed2268d3d60b24cefe2; it is not the
Linux binary pinned by the release workflow. The installed Arduino packer has
identical bytes and reproduces the same failure. Outputs are retained only as
.failed-partial evidence. No successful image readback or complete image is
claimed. Qualified Linux packing or a separately reviewed packing repair is
required; arithmetic fit is not physical image qualification.

No hardware, flashing, partition resizing, app removal, GitHub publication or
upload occurred. Existing earlier checkpoints remain available.
