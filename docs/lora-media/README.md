# Waveshare LoRa external-media repair

This independent release complements the frozen `test-app-crash-sdr-0.1.45`
firmware. It neither rebuilds nor uploads firmware assets. The source producer
is System Apps `fe238022814c89e3c7cafb3df60a3997e34caf7b`, selected with
`--product wave-media`; its `docs/shared-app-crashes/replay/LORA.md` records the
exact source closure and byte-identical predecessor reconstruction.

`source-pins.json` binds the official predecessor card, fixed ELF and Runtime.
`upstream-cohort.json` preserves the source producer's original receipt verbatim;
only its single `apps.lora_messages` record and capability universe are consumed.
Inherited totals outside that record are not asserted as this media product's
counts. The original firmware manifest and policy are retained as read-only
qualification references. The package changes no firmware files or grants.

Run `scripts/test_lora_media_release.py`, then `scripts/package_lora_media.py`
with explicit `--baseline`, `--system`, `--runtime`, `--compiler`,
`--source-revision`, and a fresh `--output`. An optional `--source-cache` maps
recipe repository IDs to local Git object stores; it never selects working trees.
The package exports the pinned replay recipe into an isolated directory and
rebuilds the final ELF before staging the card. It emits a deterministic card
archive, evidence archive, release record, installation text and checksums.

The dedicated GitHub Actions workflow runs the same qualification and publishes
a new prerelease, refusing existing tags/assets. Its contents-write permission
is restricted to the publication job. No factory-flash action is provided.

The internal catalog may continue to display its frozen 0.1.16 manifest version;
the external media manifest and companion release identify the 0.1.17 binary.

The historical standalone renderer fixture omits the trailing runtime API
`confirm_boot` member. Both source versions retain the original compile failure
and a host-only `-Wno-missing-field-initializers` compatibility attempt. C
zero-initializes that member. Both then fail the same `radio_sends==1` assertion
in `send-history`; the assertion and production code are unchanged. This is a
recorded inherited failure in that nonselected legacy feature profile, not a
passing test. The positive renderer gate uses the current production shared-input
fixture with all selected target defines, including send-history, modal policy,
unavailable service and retained callbacks, in normal and ASan/UBSan modes.
