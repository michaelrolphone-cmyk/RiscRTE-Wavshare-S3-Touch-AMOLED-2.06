# Provider CI dependency closure

The provider workflow on main at `3fe09c68019cd8d258789eb903d55c6b9bfbbe10`
failed when its standalone-C glob selected `test_storage_async.c`. That test
requires Runtime storage ABI headers, FatFs linkage and three runtime cases.
The same glob also selected the export and USB integration tests, which have
additional required sources. All four storage tests already have dedicated
runners; the provider workflow now invokes each explicitly, normal and sanitized.
The generic runner retains the other nine physical-provider tests.

This defect was present in the verified 0.1.46 source: the old workflow,
`test_drivers.py`, and `test_storage_async.c` blobs are identical in 0.1.46 and
0.1.48. It is separate from the successful native-face and launch-brightness
release pipelines. No published release tag, asset, payload, driver, hardware
profile or runtime firmware is changed by this source/CI repair.

## Header ownership

Watch remains pinned to `e49a3da30682eef7bf55716fa8223ac615eebb02`; its driver
helpers are needed, but it does not own `RiscStorageWorkerV1.h`. Runtime advances
to the already source-qualified 0.1.48 Runtime pin
`4107eaeedd8c801eeaf7deb1c7bc4a943cd27342`, whose optional storage suffixes match
the test's capacity/admission checks. Runtime supplies the current generic ABI.
System and Drivers pins remain unchanged.

`prepare_provider_test_sdk.py` stages one copy of each header for integration
harnesses. Passing both original roots as include directories is unsafe: quoted
includes can instantiate two different `#pragma once` provider type definitions.
The five nonidentical Runtime overrides are recorded with exact old/new SHA256
values in `header-overrides.json`; an unexpected, changed or stale collision
fails closed. All selected header paths and hashes are emitted as
`provenance.json`. The product storage ABI prefix must match Runtime byte-for-byte.
Standalone non-storage tests retain their original include paths. Synchronous storage tests and physical-provider target builds also use the flattened SDK because the existing FatFs extensions depend on Runtime-owned filesystem headers.

The regression unit suite requires every specialized runner to be present in CI
in both modes, checks the standalone/specialized partition, and tests identical,
reviewed, unexpected, altered, stale and nonempty-output SDK cases.

Host models and target loader validation do not qualify physical hardware.

## USB integration pins

The existing USB harness now runs with Reader
`322fc9c0fbe6713a9fc0f3175a19550970682eaa` (MSC 0.1.8, including the
unaligned-access sanitizer repair) and upstream TinyUSB 0.16.0
`1eb6ce784ca9b8acbbe43dba9f1d9c26c2e80eb0`. Reader's preparation script enforces
the TinyUSB commit and clean source before applying its source-owned patch.
Reader is checked out sparsely for the required scripts, SDK, fixture and driver.

The synchronous storage build excludes unused optional async helper functions
from warning-as-error checks, matching its specialized async runner's existing
warning policy. All other warnings remain errors. The complete SDK is searched
before product fallback headers to keep each ABI type defined exactly once.
