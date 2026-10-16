# T054 cumulative preference candidate

Builds on the exact .35 T053 full image. Rebuilds every available namespace-1 application with explicit USER and AUTOMATIC preference paths, preserving the actual deployed Home, Settings/tap calibration, T030 Springboard, T052 Files, Wi-Fi, spectrum/Waterfall and productivity app sources. Contexts retains runtime catalog routing and focus restoration. Unavailable manifest-only apps remain unavailable. All other providers and store bytes are retained.

Native Runtime c258c4b selects 23 exact writer rows, 32 native writer capacity and 34 Runtime atomic bindings. General preferences use namespace 1; Wi-Fi retains namespace 6 and SD volume 12. Fresh-internal fallback is selected only under the qualified Fresh receipt protocol; legacy uncheckpointed state still needs valid SD reconciliation. Target build succeeds at 77,332 static RAM bytes and 1,701,769 flash bytes. Bootloader and partition bytes match the .35 baseline exactly.

The current 62-ELF store passes full Runtime/CpuPort admission with zero hardware/storage calls. Preserving-update verification must use the final assembled candidate digest. Factory images overwrite saved data; existing-device updates require a fresh complete readback and the separately generated, hash-verified inactive-bank plan. No physical device testing occurred.
