# Display-link isolation test 1

Temporary standalone diagnostic for Waveshare ESP32-S3-Touch-AMOLED-2.06 only.
It is NOT Home 0.15.0 or a claim of repaired production firmware. It leaves the
shared Home, production provider selections and T-Watch source unchanged.

The failed 0.1.3 hardware log confirms ALDO2 was already enabled at 3300 mV
before writes; reset read back LOW and HIGH. No panel response was observed.
Those results weaken the missing-rail explanation; they do not validate SPI
signals or measure connector voltage.

This one image cycles four 12-second phases, restarting deliberately between
phases so no SPI ownership/state is shared. Cold power-on starts at phase A.
Every phase uses the unmodified Waveshare-bundled Arduino_CO5300 controller
and Arduino_GFX drawing code from b099739ad0e33b34e5fbaae77f02bd84805d79a3.

A: original Arduino_ESP32QSPI backend at the vendor default 80 MHz.
B: original backend at 40 MHz (the production candidate's clock).
C: unmodified RiscRTE NativeSpi.inc at 40 MHz, through a diagnostic DataBus adapter.
D: the same native raw backend at 5 MHz, to distinguish speed-sensitive behavior.

The screen is commanded through red, green, blue and gray backgrounds, with
phase labels and an increasing frame number. Brightness is 80/255. PMIC chip,
ALDO2 configuration, GPIO pad/mux/output-route state and phase results are logged
via USB at 115200. PMIC registers are never written. NativeSpi.inc is compiled
verbatim from 8aae8df4f9139bea06ff43888ed628c45ed8a057; the raw adapter is test-only,
not a public capability or new device dependency in the shared app. This tests
the native transport core, not the full ELF loader/provider graph.

Flash `Waveshare-DISPLAY-LINK-TEST-1-full-0x0.bin` at 0x0. The full initial image
replaces the lower 8 MiB, including NVS and firmware; it is not preserving.
No separate erase or SD/network setup is needed. Use the established BOOT/PWR
procedure. After flashing, start USB capture at 115200 and leave it running
through A, B, C and D (about one minute). Report which labels/colors appeared,
if any, and the complete log. Resets between phases are expected, not crashes.

If vendor A/B illuminate but raw C/D do not, that isolates a transport-path
difference without blaming shared Home. If C/D illuminate too, the complete
Runtime/provider integration remains suspect. If only low-speed output works,
timing/signal integrity remains relevant. If nothing appears even in A/B,
this still does not prove a hardware defect: it requires validating the vendor
control on this exact panel/board, factory firmware behavior and physical path.

Compile/packaging success is not evidence of visible output. Restore the normal
RiscRTE firmware after this diagnostic; it contains no apps or normal watch UI.
Vendor source retains its original license; no vendor source files are altered.
