# Waveshare Deep -3 lifecycle repair

This directory prepares the 0.1.54 successor to the immutable 0.1.53 release.
The user observed `Sleep Err Deep -3` on 0.1.52 and reported that they had not
used serial SD. The exact Runtime defines -3 as BUSY. The 0.1.53 repair fixes a
separate untimed-sleep INVALID(-1) dispatch defect.

The user subsequently confirmed that no SD card was inserted. Their only
interaction since installation was Battery Status, then returning Home, followed
by an untouched sleep/wake loop. The mounted-SD defect described below is a
separate reproduction; its absent-card control enters modeled Deep and therefore
does not explain the reported no-card sequence on its own. The current priority
is post-Battery resource/ownership cleanup and the remaining BUSY guards.

`released-baseline.json` records every file extracted from the public 0.1.53
factory image. The independent read-only decoder found 128 files and 62 ELFs.
The paired firmware and store extracted from that factory match their published
standalone assets byte-for-byte. This is an artifact-preservation baseline,
not hardware evidence or qualification of the pending 0.1.54 implementation.

The lifecycle investigation covers automatic startup mounting, without a user
serial transfer. A mounted idle SD controller can conflict with native Deep
readiness, which requires it closed. The source repair must preserve readiness
and ownership guards and provide checked preparation and reversal at the owning
Runtime/provider boundaries. Other BUSY guards remain relevant until the exact
hardware path is identified.

Required software evidence includes a failing pre-fix reproduction, idle-mounted
and absent-card cases, active-transfer/open-handle refusal, partial preparation
rollback, Light resume, Deep commit, owner/token misuse, complete final-store
admission, unchanged unrelated payloads, final native linked-memory fit and exact
published bytes. Factory installation erases internal saved data. Hardware
testing remains a separate outcome.

Baseline release:
https://github.com/michaelrolphone-cmyk/RiscRTE-Wavshare-S3-Touch-AMOLED-2.06/releases/tag/test-sleep-rebound-0.1.53

Active defect:
https://tasker-workboard.hazy-auk-4334.chatgpt.site/?task=eb70f59f-e7b1-49e4-a5bd-d63c3d59bf03
