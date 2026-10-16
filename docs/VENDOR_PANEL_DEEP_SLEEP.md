# Vendor panel deep sleep

The selected vendor panel previously returned RISC_DEEP_SLEEP_UNSUPPORTED (-7)
unconditionally. The provider now closes the native transport, then claims its
configured active-low reset through platform.gpio and holds it LOW across deep
entry. The GPIO dependency is explicit in the provider manifest.

On refused sleep, resume unholds and releases reset before reopening and
redrawing the vendor panel. A failed unhold/release retains the exact token and
blocks normal operations and unload. Fresh startup briefly claims reset LOW
through the scoped native GPIO implementation, which stages the latch before
releasing the electrical hold inherited from deep wake, then releases the token
before vendor open. No hardware ABI, PMIC settings or native sleep barrier changes.

The production-provider fixture checks repeated deep prepare/rollback, close
failure, hold refusal, release failure and retained ownership alongside existing
light-sleep/full-frame checks. Normal and UBSan driver suites passed locally.
ESP32-S3 target ELF validation passed. Physical wake/current testing remains due;
no device was flashed or accessed.
