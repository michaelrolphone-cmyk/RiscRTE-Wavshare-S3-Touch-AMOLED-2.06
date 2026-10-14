# Waterfall full-Contexts startup storage

The Waveshare 0.1.26 log stops after fingerprints begin. The private RF event-file proxy already borrows and releases each storage.app-data operation. The deployed Waterfall policy nevertheless lacks storage.shared-data grants. cfa_restore invokes portable_contexts_models_save, whose initial full-service checkpoint requests namespace 2 first, then RF namespace 3 and rules namespace 4. The missing grant triggers terminal native custody retention with no live private storage lease.

Reproduction: actual Waterfall restore, full Audio/RF Contexts service and production custody adapter, with the deployed feature flags and a Runtime model enforcing one app/shared lease. The pre-fix denial run reaches namespace 2 with live_appdata=0, retains twice and fails the terminal-callback assertion. Corrected provisioning supplies only the two context-fingerprints.cfp grants and context-rules.ctx grant. Runtime exclusivity and retention remain unchanged.

Waterfall temporal_retained now observes both native adapter retention and its private scope. A failed shared checkpoint cannot call notify/timing afterward. Build against System Apps 088c88bd2ffee0c38fd3b07631a1713c5ca85146, which already guards Contexts callbacks and polling after native retention.

The full-service regression covers fresh startup, checkpoint-first and repeated shared/private operations, refused fingerprint cleanup and deployed-policy denial, in normal and ASan/UBSan builds. No RF capture or microphone opening is allowed in this startup fixture. Physical device validation remains outstanding.
