# Waveshare integration candidate 0.1.8

Work in progress: this candidate composes the full watch UI feature profile,
real audio/RTC/alarm/Contexts/BLE telemetry providers, and provisioned GPIO
crown recovery. Shared UI source pins and exact cross-product Home ELF identity
must be finalized before delivering a binary. No hardware qualification is
claimed. The CI image is not a release or a request to flash.

The assembled file covers the lower 8 MiB at address 0x0, including erased NVS.
Original display startup probes remain enabled. LoRa and infrared hardware are
not provisioned. Display sleep/wake is not yet qualified.
