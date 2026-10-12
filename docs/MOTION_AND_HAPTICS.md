# QMI8658 motion and ERM haptics

`motion.accel@1` and `haptic.effect@1` are the same public capability IDs used by other implementations. The new providers contain no board pin numbers; physical binding is selected by the device profile.

The QMI8658C implementation configures a 4g/125Hz accelerometer and returns coherent signed milli-g samples. Its optional tap interface uses the chip's command/acknowledgment protocol with bounded waits, 500Hz tap sampling, configurable threshold and an arbitrary declared profile accepted by shared Home. Register state is restored before wake enrollment is removed. Pending-wake observation reads the GPIO without clearing a peripheral event. Failed cleanup retains the claims; a retained native wake error stops further I/O.

Tap observation distinguishes double taps, but the chip's tap interrupt may also wake on a single tap. This implementation does not claim double-tap-only sleep wake, measured false-positive rates or current consumption. The gyroscope is not yet exposed through a separate generic capability.

The schematic has an ERM motor on GPIO18; the earlier README statement that this board lacked haptics was incorrect. The generic GPIO haptic provider maps existing effect IDs to bounded pulses. This preserves notifications, not exact DRV2605 waveforms. The provider turns the motor off on stop, teardown and pulse expiration; unsuccessful writes preserve cleanup state.

Host tests execute the actual C drivers and cover every tap-configuration I/O failure, bounded command timeout, retained wake state, coherent conversion, both motor polarities, an alternate configured pin, pulse expiration and failures that can occur after an output write. All six physical providers compile with the pinned Xtensa compiler and pass the real ELF structural validator. These results are software tests, not physical-device qualification.

Protocol reference: Waveshare example bundle b099739ad0e33b34e5fbaae77f02bd84805d79a3, SensorLib SensorQMI8658.hpp and QMI8658Constants.h; QMI8658A Datasheet Rev A section 10.5. SensorLib's MIT notice is retained in THIRD_PARTY_NOTICES.md.
