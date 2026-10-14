# T051 Waveshare asynchronous SD checkpoint

Working source checkpoint; not a qualified firmware delivery.

The opt-in WAVE_SD_ASYNC provider uses the shared copied-work adapter,
checked warm session admission, ordinary-handle fencing, and native capacity
suffix. DAT3 stays high; activation performs no card I/O. Default synchronous
mode remains available. Shared FatFs source is recorded in
provenance/storage-t051.json (Drivers 11bc45d263f830c70cea53a8c8749e4fcf17b041).

## Validation

The actual provider/FatFs RAM-card test passes in a normal host build.
It covers zero-I/O activation, rejection with an ordinary file open, fencing
ordinary access during a copied session, small writes and reads, three clean
session re-entries, and resource release. Payloads are synthetic strings,
not the Wi-Fi profile codec. The worker mailbox and transport are host fakes.

Reproduce with scripts/test_storage_async.py --sdk UNIFIED_SDK
--support-include PRODUCT_INCLUDE [--sanitize]. The tested SDK was staged from
Runtime ce5ad0c838cb39f1bb19ca20e13984319b972842 over the existing product SDK.

## Incomplete qualification / integration

- Actual Runtime storage pin, native settings lifecycle, maintenance and
  startup qualification with this provider remain incomplete.
- The deployed boot recipe still needs an installation-volume declaration
  for SD instance 12 and explicit namespace 6 policy review.
- End-to-end multi-network profile save, cold restart, edit/delete and injected
  faults through the actual Wi-Fi controller and deployed SD remain unqualified.
- Target provider build, final cohort assembly/admission and release are pending.
- No hardware, serial, flashing or physical card testing has been performed.

Preserve ordered input, Springboard, native geometry, SDR and other applications.
Do not use this checkpoint as evidence of release readiness.
