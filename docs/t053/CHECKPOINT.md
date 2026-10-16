# T053 implementation checkpoint

This is an incomplete integration checkpoint, not firmware qualification.

Waveshare raw SD export and existing async storage tests pass normal and Linux ASan/UBSan runs. Shared MSC normal suite passes. The shared MSC sanitizer run fails in pinned TinyUSB tusb_common.h:264 on an unaligned uint32_t load. Native USB PHY test fails at usb_phy_port_test.cpp:47 on providerStorageSafe() after retained release. Both remain to be repaired and rerun; raw failures are preserved in the corresponding repositories. RGB USB presentation tests and product packaging remain pending.

Preserve Windows host safe eject, CSW completion before teardown, explicit cable-removed fallback, retained uncertain I/O, and generic storage export. No hardware throughput or serial-restoration result is claimed.

## Repair and integration results

Actual Waveshare SD/FatFs + shared MSC/TinyUSB integrated tests pass normal and ASan/UBSan. Read/write sizes 1, 2, 7, 8, 9, 15, 17 and 128 sectors preserve exact bytes and restore original test sectors. Host eject waits for CSW completion before USB stop, remount and PHY release; explicit controller unplug follows checked cleanup. Local file writes work after cleanup. Native media, DCD and PHY are modeled; hardware qualification remains outstanding.

## Cumulative product admission

Waveshare 0.1.35 admits all 62 ELFs with zero hardware/storage calls. The native build uses the unchanged product native/VendorDisplay.cpp and byte-identical staged vendor library from the 0.1.34 native baseline; the release evidence includes its full hash inventory and build inputs. The new native profile links the USB PHY marker. The earlier incomplete native build without the vendor overlay was discarded.

X4 0.1.118 admits all 43 internal ELFs against unchanged native a91edf3fada6a559ec107186dd163d0c8da10d29 and checks the cumulative SD OBD Dashboard, OBDTest, Buttons and new MSC image. Both products use USB app 0.1.11 (above delivered resident 0.1.10), MSC 0.1.8; Wave SD is 0.2.1.
