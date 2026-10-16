# T051 native storage and Wi-Fi qualification

`run.py --root STAGED_ROOT [--sanitize address,undefined]` builds actual Runtime,
CpuPort, native settings lifecycle/maintenance/bootstrap, checked replica stores,
Waveshare SDMMC/FatFs provider, and the System Wi-Fi controller. Stage the selected
Runtime as `runtime`, this product as `wave`, System as `system`, merged SDK as
`sd-sdk`, product DriverSupport headers as `support`, and deployed board.json
under `store`. `prepare.py` derives the fixture from Runtime's checked maintenance
harness, replacing board pins/volume and selecting only namespace 6.

The tests use simulated RTOS scheduling, vendor NVS and RAM-backed SD transport;
native replica files are real host files. They retain native files, serialized
NVS metadata and the card image across separate process invocations. Tests cover
two saved profiles, repeated controller opening, cold restart, edit and deletion,
another cold restart, SD acknowledgement, fresh native baseline/first checkpoint,
and unchanged namespace 1 native metadata. First-checkpoint capacity authority is
supplied by the existing host fixture; physical card capacity is not qualified.

No target instructions, physical radio, display, flash or SD hardware are exercised.
Normal and Linux ASan/UBSan runs are required. The separate provider tests cover
missing media, failed close/retained resources, copied requests and owner fencing.
