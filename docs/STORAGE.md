# Generic SD-card volume

The `storage_sdmmc` provider exposes `storage.volume@1` and consumes generic scoped SDMMC/GPIO, clock and synchronization interfaces. Pin selection is exclusively in the device descriptor: CLK, CMD, DAT0 and DAT3. The fourth pin is held high during initialization to select SD native one-bit mode. No device-prefixed capability or application pin assumptions are introduced.

The existing Reader FAT core at 3f59913963840cb5ee8e2a65baa921f8d6af0b4d is imported unchanged, with its license and a file-hash provenance record. No automatic formatting is performed. Empty/unformatted media yields an unavailable volume without preventing provider startup. A missing card can be retried through refresh.

Open file/directory handles prevent unload. Card release, DAT3 release and synchronization destruction happen in order; incomplete cleanup preserves its tokens. An uncertain write prevents subsequent writes instead of retrying a possibly completed sector. A failed owner-lock release retains the implementation. The existing FAT operation limits and copied native one-sector I/O are retained.

Normal and address/undefined-behavior sanitizer tests use the actual provider and FatFs on a RAM-backed FAT32 card. They exercise mount, read, write, seek, directory enumeration, long names, rename, remount, no-card startup, owner restriction and cleanup failures. Nine successful-path sector write boundaries are interrupted in separate processes, with no blind write retries. This is filesystem/transport-model evidence, not physical SD-card qualification.

Runtime needs RISC_ENABLE_SDMMC; the universal build environment enables it. The physical board wiring permits the one-bit transport, but the vendor demo initializes cards in SPI mode. After running SPI firmware, a card power cycle may be necessary before SD-native initialization. Actual card/board compatibility, electrical timing, sustained throughput, and deep-sleep media recovery still need device testing. No storage power-domain shutdown/resume support is advertised by this initial volume provider.
