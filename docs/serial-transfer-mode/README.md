# Dedicated serial transfer mode successor preparation

Selected versions: Runtime0.4.17, Home0.20.4, Waveshare0.1.64. Runtime and Home source checkpoints are published; the exact source pins are in source-pins.json. Complete native firmware/package qualification and the .64 feed publication remain required before delivery.

`build_serial_transfer_inputs.py` is the successor input producer. It passes `--serial-transfer-mode` and `--automatic-provision` to both independent default-role Home builds and checks the actual compiler receipt. Home0.20.4 is selected only when the new option is enabled; other profiles retain0.20.3/0.19.3 and the unchanged clock-return role. The new serial-transfer-native.cmake profile opts in with `RISC_NATIVE_SERIAL_TRANSFER_MODE=1`. The producer's `runtime_selection` requires exactly this definition in every actual Runtime compilation row; a complete fresh native build must call it before claiming product qualification.

Inputs are the exact released .63 store and external archive. Only default.elf, default.json and installed-apps/driver.elf are replacement inputs. The catalog must differ solely by the .63-to-.64 feed URL; its manifest is retained. The receipt records all other107 internal files and all45 external files. Cohort metadata will change only during firmware-bound package composition. The historical .63 producer remains untouched and cannot accept the new Home.

Existing HELLO enters a dedicated owner mode before success. Users reset manually after transfer. No new browser command, automatic reset, idle-SID timeout exemption, or data-loss behavior is added. Normal30-second protocol expiry remains recoverable with a fresh HELLO while the device stays parked. Namespace2 can remain usable when SD namespace12 is absent.

Local target Home/catalog build receipts do not qualify the full Runtime firmware link, physical USB/SD, transfer timing, watchdog behavior, or device recovery. No hardware action was performed.

The additive .64 release recipe selects both mode flags, rebuilds Home twice, retains external bytes, and checks native Runtime compile commands before publication. The historical .63 scripts, profiles and workflow remain byte-identical.

Ordinary explicit Replace never requires prior size/hash identity. The known-lora mixed plan replaces exactly three selected paths and creates the remaining42; all-replace selects all45 paths. Both verify the new bytes. A separately named conditional-known-lora variant retains optional prior-identity guards and must never be substituted for ordinary Replace. Create and Verify remain non-replacement operations. No automatic plan selection or browser implementation change is claimed.
