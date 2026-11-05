# Wave shared Wi-Fi native dependency

This additive qualification recipe is based on the already-qualified capacity-only
native dependency at 97ca6157aa9c3bba7c7fee3858aa7d0ff896d13b (PR31).
It selects Runtime 532c502fb2aad358d46166d5fd1df8358148f20e (0.4.23).
Existing recipes, release defaults, provider graphs and settings authority are
unchanged.

The derivative explicitly selects ExternalVolume with LOCAL_ONLY=0 and
LOCAL_FRESH=0. The unchanged native settings header retains volume12, its
WAVE-RTE-WIFI logical identity, namespace1 and6 writer registrations, namespace
mask3, max writers32, atomic bindings34 and checked internal-fresh fallback.
The complete transfer/provisioning profile, provider48/platform32/app-grants16,
SDMMC, USB PHY, radio IQ, HTTP, two settings workers and the released partitions
remain selected. Fresh fallback is the existing ExternalVolume behavior; it
does not change replica acknowledgment obligations.

Qualification requires a fresh controlled SDK6.1/GCC15 build in the same process,
all original source-closure, linked-capacity, IQ and ELF/BIN checks, an evaluated
profile delta and preprocessing the actual Backend compilation command. It also
verifies the exact released0.1.64 baseline and its volume12 owner/installation
authority without modifying that baseline.

The released0.1.64 store is not the shared-Wi-Fi historical companion store:
the former has SHA256 0d6a414a15ad34c92cc3d5a511b601fa2cbc1e1c7ba6b1b29e9c18b8ec596f93,
the latter f92a9de1a8fb050b636476ff703ce68fa083a81c452b3ec82259f512733af64b.
This recipe emits only a native dependency, not an installed-product admission,
new app/store composition, release, update kit or hardware result. Complete
shared-Wi-Fi graph admission, saved-data/lifecycle proof, live heap/stack/shared
AppData capacity and physical qualification remain separate. Host tests do not
establish those outcomes.

Run scripts/test_shared_wifi_native.py for profile and macro rejection tests.
The isolated workflow builds and retains linked artifacts and source custody;
it has read-only repository permissions and no publication step.
