# Waveshare cumulative launch-brightness media companion

The same 0.1.48 source commit owns this LoRa 0.1.18 companion and the firmware.
The packager checks the actual firmware factory, release metadata, cohort,
unchanged boot grants and internal LoRa admission manifest. It then strictly
replays the wave-media recipe from System 24270c36 and preserves the prior
0.1.17 card's exact member set, changing only ELF, manifest version and content
digest. No firmware, internal manifest, permission or volume-route update is
performed by this companion. The media package is attached to the same
0.1.48 release, not to a new independent tag.

The source-owned tests reject payload, policy, version and archive drift.
Target replay checks all transitive inputs, symbols and capability literals.
Normal/sanitizer loader, LoRa shared-input and Runtime optional/removable-media
checks remain mandatory. Historical nonselected renderer failures are recorded
as paired negative evidence, not counted as passing checks. Device validation
is still outstanding.

Run package_launch_brightness_media.py after the main 0.1.48 firmware package,
passing --factory and --firmware-release from that same source commit, plus
--baseline (the exact published LoRa0.1.17 SD-card ZIP), --system (24270c36),
--runtime, --compiler, --source-revision, --output and optional --source-cache.
Copy all files from the resulting assets directory into the firmware release's
asset directory before regenerating its top-level SHA256SUMS and upload.
