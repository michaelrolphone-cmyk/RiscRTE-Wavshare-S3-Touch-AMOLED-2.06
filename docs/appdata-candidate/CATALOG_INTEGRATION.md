# Local catalog consumer checkpoint

Runtime c6ef4bf5e69460a2c491204c3a52795191da51fc contains the scoped published
app.catalog delta on the existing generic transport lineage. The native build
and 49-ELF candidate admission pass. No display transport source was replaced.

`scripts/stage_catalog_candidate.py` builds a separate, unsealed candidate from
the existing storage composition. It selects System
72f435fcee376ec62d17ece6180753385ea547d9, metadata helper source
362537417c4f37bbb240879d5ba756686511fec1, generic bridges
6e82fdcaec0b73ed700d2104cfb4d94f011c19d4 and unchanged Home source ec768c7.
It rebuilds Settings, Springboard, Timecard and Audio Spectrum without any catalog
C input, verifies absence of both legacy catalog symbols, and records actual
transitive compiler inputs. Existing full feature definitions, native height,
and navigation retention remain enabled. Home and clock ELF bytes are preserved.

The metadata helper copies a new store and supplies original names/icons from
the canonical 23-row presentation fixture only to existing admitted manifests.
Home and Springboard explicitly have launcher_visible:false; Clock explicitly
has launcher_visible:true, matching the original presentation fixture. The four rebuilt
consumers receive app.catalog@1 requirements and instance-0 grants, within the
existing native capacities of 32 requirements and 32 policy grants. No absent
application is invented, installed, or marked available.

Local evidence: all 36 metadata-helper tests pass. All 49 candidate ELFs pass
normal and UBSan admission against the committed native Runtime, with zero
hardware and storage calls. These are software checks, not hardware evidence.

The shared owner's exact ordered recipes are now checked in as
`profiles/shared-catalog-recipes.json`. The builder refuses Settings/Springboard
unless their pre-compaction sizes and hashes match the qualified shared proof:

| App | Linked bytes | Linked SHA-256 |
| --- | ---: | --- |
| Settings | 225256 | 4ee26705175a325f62af18e6dc98edc9e28aa51b9bf239bc946d8908cbce1385 |
| Springboard | 228136 | f33ff27719ffd1faa1fb5f671579ada881aac29c9bd4c4673779798064470b17 |

Both identities were reproduced locally. Settings now explicitly defines version
1.3.24 and its manifest agrees. The recipe includes LTO and the public forced
alarm-profile header; Springboard explicitly retains __divsf3. These are the
qualified shared recipes, not local feature changes to chase a binary hash.

Loader-metadata compaction preserves all retained loader semantics. Independent
before/after evidence comparisons pass for both apps, and normalization removed
zero relocation entries. Final Settings is 139760 bytes, SHA-256
0866d709f94e29e1f3979e41d7822b7878b2e9860e0115ef826df09a81451634;
Springboard is 146812 bytes, SHA-256
68b7a818a9c3ade67c7ec6c0621d3e30bed22e4ec8e1615615779172d5983f49.

The standalone Contexts scene app at Utilities fc0bdbb still references
portable_catalog in Apps/contexts.c:175. This differs from the shared adapter
Contexts workflow, which System 72f435f fixes. Its existing artifact is retained
without falsely claiming it has been migrated. Its source owner is preparing
the runtime consumer. Public System CI repair remains with the shared owner.

This is not a release or a complete flashable image. Final Files/Waterfall/update
composition, cohort binding, paired image assembly and hardware qualification
remain separate. No hardware or serial access, flashing, publication, or Drive
upload was performed. Existing automatic approval-review publication blocks
remain in force.
