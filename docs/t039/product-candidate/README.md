# T039 Waveshare BLE product candidate

This additive candidate consumes Utilities PR98 (0.1.31) under the exact published Waveshare 0.1.64 consumer. It is not a release and is not approved for installation.

The product owner is `waveshare-boot-owned-external-apps`. The executable remains at `Apps/ble_buttons/ble_buttons.elf` on volume 12, while the authoritative manifest and grants remain in the internal boot store. Generic installed-app staging is not this path.

Only the separate candidate's authoritative BLE manifest and mirrored manifest/executable may differ. Existing production recipes, pins, accepted bytes, firmware, boot policy and provider grants remain untouched. Full existing Runtime admission must report the real outcome, including rejection; metadata or structural checks alone do not qualify the product.

The implementation is additive; exact-head CI outcomes are recorded in the PR qualification receipt. No merge, tag, release, firmware publication, device/radio action, memory-fit or physical acceptance is claimed.

## Qualification command

The new workflow downloads hash-pinned published `.64` store/SD bytes and native ELF evidence, plus the independently transported PR98 artifact. It stages complete baseline and candidate namespaces. Candidate differences are exactly internal `ble_buttons.json`, external `Apps/ble_buttons/manifest.json`, and external `Apps/ble_buttons/ble_buttons.elf`. It emits no factory image, firmware or installable RTE package.

`qualify_t039_wave_product.py build` invokes the existing, unchanged `serial_transfer_qualification.admit_product` in normal and ASan/UBSan modes. This compiles the exact consumer Runtime and uses its full `prepare` / `validateCohort` owner/grant/provider gates, production native export table and unchanged product profile. It retains the unauthorized namespace rejection control and candidate self-admission. The separate unchanged `qualify_minimal_sd_elfs.qualify` checks all 22 external ELFs, import rejection and removable-volume snapshots against the same native consumer.

There are sixteen manifest requirements but seventeen retained BLE grants: two existing `storage.key-value` namespaces. The actual consumer uses 32-row bounds. No narrowed detached fixture or new grants replace this policy.

The output receipt distinguishes a real consumer rejection from a qualification/tool failure. Neither can produce a successful CI result. Transport verification binds the receipt digest, exact source head, complete namespace bytes and full artifact inventory. The upstream Actions artifact expires on November 4, 2026; the durable PR qualification receipt remains, but rebuilding after expiry will need the same bytes from an authorized retained source, never a silent replacement.
