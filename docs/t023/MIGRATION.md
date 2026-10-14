# T023 Wave composition checkpoint

System reproduction fixtures now pass CI at8a18063 and a2a58b5. The native Runtime checkpoint c4df70f adds explicit software dependency bindings. USB MSC remains bound only to SD12; its ELF and all36 original provider artifacts are preserved.

Composition8c76e40 preserves the.39 Home capability policy, including Contexts shared-file declarations and the supported cold start without retained-wake authority. The new shared Home, Springboard, installed catalog and internal-volume provider admit all64 ELFs through the complete native graph with zero hardware/storage calls.

The exact native V2 migration selects.39 source14470dd to.40 composition8c76e40, permitting only Home's newly required sharing of Wi-Fi namespace6 from app_store/file_browser/ota_update/wifi_settings. Exact before/after app policies are embedded; all saved data stays in place. Production admission passes. Altered source, target, owners or snapshot reject before any ELF admission or I/O. Existing migration/retry/rollback tests pass Linux ASan/UBSan.

The selected policy is in native/t023-migration-policy.h and reproduced by scripts/generate_provision_migration.py. native/t023-provisioning.ini selects it. Native build remains sourcec4df70f with this product-owned generated header. For on-device update from.39 the old firmware has no policy; a native-first bridge or independently qualified preserving host kit is required. Do not claim direct OTA migration is supported.

No release, hardware flash, or physical qualification. Feed policy, full preserving kit tests and other product qualification remain pending.
