# Restored Springboard raster optimization, Waveshare 0.1.28

Direct descendant of the actual shared launcher restored in 0.1.26. Same honeycomb controller, fonts, gestures, features, touch and physics, with less raster arithmetic. Capability-derived layout remains 240x240 or 410x502 from the same shared binary. Native firmware and every provider/app except Springboard remain byte-identical to SDR-fixed 0.1.27, including Waterfall 0.3.5 and storage grants. SD contents unchanged.

Build with `scripts/build_springboard_drag.py --baseline <0.1.27 factory BIN> --springboard <pinned ELF> --runtime <Runtime checkout> --watch-product <RiscRTE-Watch checkout> --output <folder>`. The baseline and ELF hashes are mandatory and the paired-bank image allows only Springboard ELF/manifest and cohort changes. The exact target command and compaction proof accompany the source pins; dependency pins remain those in `integration/springboard-restore/working-source-build.json`.

Host pixel-equivalence, gesture, motion and capability-dimension tests pass; host benchmark is not hardware frame-rate evidence. Hardware drag smoothness needs watch verification. Factory image at 0x0 erases saved data.
