# Native ESP-IDF 6.1 CO5300 bridge

## Source and boundary

`native/VendorDisplay.cpp` selects `VendorDisplayIdf6.inc` for ESP-IDF major
version 6 or newer. Its existing Arduino_GFX implementation remains the IDF4
qualification baseline. The native implementation is qualified against the exact
SDK revision in `native/vendor-idf6-provenance.json`, not arbitrary later SDKs.

The new implementation replaces only the device build's private transport. It
still implements the five-function `RiscCpu::DisplayBackend` interface. The
`panel_vendor` provider continues to consume `platform.display.backend`; no SPI
handles, DMA pointers, panel-specific operation, or new capability reaches an
application. Existing broker pin reservations and failed-close retention remain
in charge. The provider, shared ABI, PMIC ownership, and reset-hold contract are
unchanged.

Register order and QSPI framing follow the pinned Waveshare reference
`b099739ad0e33b34e5fbaae77f02bd84805d79a3`. Six reference file hashes and the SDK
revision `fff9895c82d744c7237be8847347bdd1b07c6643` are recorded in the provenance
file. This is a new implementation using public ESP-IDF SPI/GPIO APIs; it does not
compile Arduino_GFX, Arduino core, private GPIO registers, or private SPI types.

## Wire and visibility contract

- SPI2, 40 MHz, mode 0, half duplex, manual CS, 8 command bits, 24 address bits.
- Register commands use opcode `0x02` and `register << 8`; pixel writes use quad
  opcode `0x32` and address `0x003c00`, with big-endian RGB565 bytes.
- Each two-row update checks CASET, PASET, RAMWR and its 1,640-byte DMA transfer.
  A 410 by 502 frame uses 251 windows. CASET remains 22 through 431 inclusive.
- Normal initialization writes brightness zero before display-on and replaces
  the reference's temporary nonzero brightness with zero. Its checked black
  clear does not count as the first application frame.
- Requested nonzero brightness is deferred until rows 0 through 501 have all
  completed in sequence, including the final paired transfer. A failed final
  transfer cannot open that gate when cleanup subsequently drains it.
- `RISC_VENDOR_DISPLAY_PROBE` retains its explicit diagnostic exception: after
  the checked black clear, brightness 80, all-pixels-on for 800 ms, then red,
  green and blue for 1,200 ms each, followed by zero brightness and black. Each
  command/transfer is checked. A failed probe does not mark the once-per-boot
  probe completed. Production builds must omit this diagnostic define.
- `RISC_PERFORMANCE_TRACE` preserves phases 34 through 39 and the existing
  binary marker. Trace-disabled objects do not contain the timing marker.

## Custody and failures

The bridge records the acquiring core and task. Hardware operations and cleanup
are rejected from another owner. It owns a persistent transaction descriptor,
paired-row copy, and an explicitly internal/DMA-capable 16-byte-aligned buffer;
caller pixel pointers never survive a row call.

Each completion poll is finite (20 ms plus tick rounding). The pinned SDK requires
`portMAX_DELAY` for polling start and bus acquisition; the bridge has its own
newly created, acquired bus and queues no competing transactions. A timeout
retains the descriptor, CS, device, DMA storage, bus, and broker ownership until
completion is proved. The SDK's completed DMA-failure status is distinguished
from an in-flight timeout. An unclassified completion error retains ownership
permanently rather than guessing that hardware stopped.

Close finishes any retained transaction, sends checked display-off/sleep commands
with their delays, releases the acquired bus, removes the device, frees the bus,
and explicitly resets each owned pad. A failed step retains all remaining
resources and the failed pad's identity. The DMA buffer is freed last. Successful
shutdown commands and pad resets are not repeated on retry. A failed bus
initialization does not claim or reset another owner's SPI pads.

## Staging

Use a clean native Runtime checkout and the pinned vendor and SDK checkouts:

```sh
python3 scripts/stage_vendor_display.py --vendor /path/to/vendor \
  --idf /path/to/esp-idf --runtime /path/to/runtime
```

This verifies both revisions and all six reference hashes, then stages only
`src/VendorDisplay.cpp`, `src/VendorDisplayIdf6.inc`, and a machine-readable
`native-display-idf6-staging.json` with hashes of the staged implementation.
It rejects a Runtime already containing `lib/WaveshareVendorGfx`. Without `--idf`,
the original legacy staging path remains available. Native Runtime's component
must depend on `esp_driver_spi` and `esp_driver_gpio` and use its existing SDK
configuration; this stage does not alter configuration or invoke a build.

## Executable checks

Configure the native Runtime once to obtain its actual `compile_commands.json`.
Then run:

```sh
python3 tests/test_vendor_idf6.py --idf /path/to/esp-idf \
  --compile-commands /path/to/runtime/idf/build/compile_commands.json \
  --vendor /path/to/vendor --output /path/to/evidence
ASAN_OPTIONS=detect_leaks=0 python3 tests/test_vendor_idf6.py --host-only \
  --sanitize --idf /path/to/esp-idf \
  --compile-commands /path/to/runtime/idf/build/compile_commands.json \
  --output /path/to/sanitizer-evidence
python3 tests/test_vendor_native.py
python3 tests/test_vendor_boot.py
python3 tests/test_vendor_timing.py
```

The test runner compiles the complete production source against real SDK SPI,
GPIO and heap headers and the actual shared Runtime ABI, replacing only host
RTOS scheduling declarations. Host implementations model transport completion
and inject faults; they are not substitutes for target compilation. The runner
also compiles four actual Xtensa target objects, one at a time, using the
Runtime's exact target command with trace/probe off/on, and verifies SPI symbol
references and absence of Arduino dependencies. Commands and logs are saved.

Host cases cover admission, exact command framing, offsets, caller-buffer copies,
all pixel bytes, startup darkness, full-frame visibility, owner rejection,
setup failure, pending timeout, completed DMA error, unknown completion error,
CS failure, failed sleep, remove/free/reset failure, cleanup retry, and timing
aggregates. Separate probe cases check RGB bytes, dwell times, and retained
faults at five diagnostic boundaries. Staging tests reject the wrong SDK and a
mixed Arduino/native library tree. Existing provider lifecycle tests remain
applicable without a provider change.

These are source, host-contract and target-object results. They do not qualify
physical panel output, electrical timing, sleep-current behavior, or a complete
linked firmware. Hardware qualification remains required before publication.
