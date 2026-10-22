# T039 Waveshare BLE product candidate

This additive candidate consumes Utilities PR98 (0.1.31) under the exact published Waveshare 0.1.64 consumer. It is not a release and is not approved for installation.

The product owner is `waveshare-boot-owned-external-apps`. The executable remains at `Apps/ble_buttons/ble_buttons.elf` on volume 12, while the authoritative manifest and grants remain in the internal boot store. Generic installed-app staging is not this path.

Only the separate candidate's authoritative BLE manifest and mirrored manifest/executable may differ. Existing production recipes, pins, accepted bytes, firmware, boot policy and provider grants remain untouched. Full existing Runtime admission must report the real outcome, including rejection; metadata or structural checks alone do not qualify the product.

Implementation and exact-head CI qualification are pending. No merge, tag, release, firmware publication, device/radio action, memory-fit or physical acceptance is claimed.
