# Waveshare 0.1.30 T051 Wi-Fi

Wi-Fi uses the shared keyboard and saves multiple network profiles through
native durable namespace 6 with acknowledged checkpoints on SD volume 12.
Namespace 1 retains its previous route. Ordered input, restored Springboard,
410x502 geometry, SDR and every other application ELF remain byte-identical to
0.1.29. The native Runtime, Wi-Fi ELF and SD provider are updated together.

Host qualification uses the actual Runtime/CpuPort/lifecycle, checked native
stores, System Wi-Fi controller and Waveshare SDMMC/FatFs provider. It covers two
profiles, app re-entry, cold process restart, edit/delete and another restart,
fresh baseline/first checkpoint, SD acknowledgement and namespace 1 isolation.
Normal and Linux ASan/UBSan pass. The SD provider's normal and sanitizer fault
regressions pass; synchronous mode passes nine write-cut cases. These tests use
simulated vendor NVS, scheduling and card transport, and host native files;
physical flash/radio/display/SD and target execution have not been tested.

This is a factory provisioning test release, written at 0x0, and erases data.
Existing SD application content is unchanged; no changed-SD archive is needed.
Full Runtime admission and exact assembled-image readback are release gates.
