# Display-link hardware result

The owner tested `Waveshare-DISPLAY-LINK-TEST-1` and reported:

- A: Waveshare-bundled Arduino_ESP32QSPI at 80 MHz — visible display works.
- B: the same vendor backend at 40 MHz — visible display works.
- C: existing RiscRTE NativeSpi.inc at 40 MHz — no visible output.
- D: the same native backend at 5 MHz — no visible output.

All four phases use the same vendor CO5300 controller/drawing source and physical pin mapping. This identifies a failure associated with the native transport path; it does not identify the precise internal cause yet. The panel can operate with the vendor backend on this board. The previously proposed missing-ALDO2 explanation is not supported by the later PMIC readbacks and these successful reference phases.

Do not report native display recovery based only on host models, successful SPI completion, `first-frame`, or `services-ready`. The corrective build must retain the shared generic `display.output` application boundary and be tested against the observed vendor/native difference.
