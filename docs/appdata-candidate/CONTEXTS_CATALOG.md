# Standalone Contexts catalog composition

The exact qualified Contexts app was built from Utilities
186ba80899fc9746609860821df61c7bbe0e2dc8 with the repaired scene/text SDK at
System f4b30f8ebcc6d8cb905c8e90c91b1691acbe8165, the three catalog client headers
from System b580e32, and the 34-face header from Watch 6e82fdca. The public
build_contexts_scene.py was used with --target watch --shared-text-input and
no compiled catalog input. Target validation and the complete ELF catalog-symbol
rejection passed. The result exactly matches the shared owner's 88020-byte ELF:
8db9d4be5801635bdb58e3f5ddaa41bcbdb744243a0e875a4a8252496cd24402.

`scripts/stage_contexts_catalog.py` stages this exact app into a fresh local store.
It preserves every existing provider file and app grant, and adds app.catalog@1
instance 0. The qualified app also requires ui.text-input@1, absent from the prior
28-provider composition. The script builds and adds that provider from System
f4b30f8, plus its instance-0 app grant. Existing utility-service/provider pins are
not replaced. Authoring-only manifest fields are removed; Runtime-admitted
presentation, version, requirements and minimum-firmware metadata are retained.

The composition now contains 21 apps and 29 providers. Native admission and ELF
validation are software checks. The new text provider and the existing scene
provider at 1aaf53e are a distinct composition from the shared owner's repaired
scene/text host test cohort. Their combined keyboard/policy behavior needs
qualification before delivery; passing admission alone does not prove it.
The app retains its declared 95-row chooser bound; 96–128 rows fail visibly
instead of truncating. The current admitted inventory is below that bound.

This is not a final firmware image. Remaining Files/Waterfall/update composition,
paired image assembly, public source CI and hardware qualification remain separate.
No flashing or remote publication is part of this checkpoint.
