# Qualified artifact publication without recompilation

## Provenance policy

The release tag points to the **immutable producer commit**. A publication commit
authorizes use of that producer; the controller commit provides the promotion
implementation. These are distinct identities. `release.json`, `SHA256SUMS`,
qualification, source locks, CI snapshots, and every binary remain byte-identical.
The additional `publication-envelope.json` binds the original manifest, archive,
all original assets, provider run/attempt/repository/workflow/artifact identities,
audited build-input closure, publication source and controller source.

The original manifest's `publication_enabled: false` and `native_rebuilt: true`
are historical producer facts. They are not rewritten. The envelope records
`publication_native_rebuilt: false`. Neither document claims hardware testing.

Trust comes from a committed authorization read back from the exact main commit,
the exact repository-owned successful GitHub push-run attempt, the provider's
immutable artifact ID/archive digest, and the original clean producer verifier.
The envelope is verified against those sources and exact bytes; it is not an
independently cryptographically signed attestation. A hash alone is not authority.

## Audited input closure, initially Wi-Fi footer v1

The initial policy deliberately admits the existing Wi-Fi footer recipe only.
Its audited source is `30d8c5f75cf809d28fe01d8691ec6fe372856af0`.
The producer must exactly equal that audited commit, including its full document
tree and file types; a new producer cannot inherit the audit through equal code
alone or introduce a documentation symlink/alias. `wifi-footer-audit.json` also
pins the entire non-document tracked tree, including
modes and gitlinks, plus every build/dependency/compiler/configuration pin.
Unknown producer code or dependency pins require a new explicit audit.

Between producer and publication revisions, **every** tracked entry must match,
including additions/deletions, modes, submodules and unclassified documentation,
except:

* `docs/wifi-footer/source-pins.json`: only the boolean `publication_enabled`
  may change from `false` to `true`. Both recipes must already be finalized.
* Three ordinary non-executable documentary files:
  `docs/wifi-footer/retained-touch/README.md`, `normal.json`, `sanitized.json`.

This is an exact path/field allowance, not a `docs/**` exemption. Audit of the
pinned native runner, packaging, qualification and transitive source paths found
no consumption of those three retained-touch documents as build inputs. Their
changed blob identities are retained in the envelope. Source-pins normalization
does not change the producer file, its source lock or its manifest.

Any firmware, dependency, compiler, configuration, workflow or unknown input
change fails closed. Use the existing `wifi-footer-native.yml` native build and
qualification route for changed inputs. No automatic rebuild is started by a
failed promotion. Supporting another product recipe requires a reviewed audit
profile and its existing source-pinned verifier, not a caller-provided exemption.

## Run a promotion

1. Commit a strict request JSON under `docs/release-artifact-reuse/requests/`.
   It must contain the exact producer and publication commits, repository,
   successful run ID/attempt, immutable artifact ID/archive SHA256, original
   `release.json` SHA256 and `SHA256SUMS` SHA256. See the qualification request.
2. Run **Qualified artifact publication** on main, selecting that committed
   request. Leave the workflow `publish` input false to verify without writes.
3. Publication requires both the committed request's `publish: true` and the
   explicit workflow `publish` input. It never creates a new version, tag alias,
   replacement asset, feed, catalog entry, target build or device operation.
4. The controller fetches the exact attempt, checks success and qualification,
   expiration, repository/workflow/source/artifact identities, downloads the ZIP,
   verifies its provider digest and size, checks bounded safe inventory, and runs
   the original producer verifier on an exact clean checkout.
5. It rechecks every original asset and the envelope during draft reconciliation,
   after upload and again from independently downloaded public assets. Existing
   tags, version reservations, release title/body, assets and all bytes must
   match. Interrupted draft uploads add only missing assets. Uncertain creation
   uses the corrected bounded read-after-create helper; it never recreates a
   release automatically. Errors propagate without silent retries.

Requests are immutable under their controller commit. Changing request intent,
source, identity or hashes requires a new committed revision. A request cannot
load Python from artifact contents. The producer verifier runs only from the
audited repository source. Standard Python and GitHub CLI suffice; no ESP-IDF
container or compiler is provisioned by this workflow.

## Qualification and measurements

The historical no-write fixture uses producer run `38991612546`, attempt `1`,
artifact `12085796024`, archive SHA256
`17d8eadb584ecd4a70f8d297b6d5df13faab21719e3ad931b855a4f4083434db`.
The provider reports expiration at `2026-11-16T01:44:59Z`; once expired it must
reject. Refreshing this fixture needs a genuinely eligible immutable artifact,
not an override of expiration. Main push qualification publishes only a CI proof
artifact, never firmware or a public release.

All 21 original asset bytes passed a local replay using the unchanged producer
verifier on 2026-10-19. Local replay, excluding remote transfer, took about 0.56 s.
GitHub's historical native build-and-qualification step took 395 s and its native
job 489 s. These are distinct measurements on different machines, not isolated
compile CPU savings. CI writes its measured wall, user/system CPU and peak RSS
with explicit scope in `promotion-result.json`. A real publication adds network
upload and independent readback time and is not represented by local replay time.

The existing `.55` tag points to its later rebuilt publication source, so
promoting the original producer under that tag is correctly incompatible. The
qualification request has `publish: false`; it cannot modify that release. The
offline suite exercises full publication, immutable tag refusal, interrupted
upload resume and final public-byte verification with a synthetic remote.
No new firmware stream is created for this qualification. Deployed `.64` bytes
and every independent hardware fixture hold remain unchanged.
