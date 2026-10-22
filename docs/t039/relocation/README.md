# T039 production Xtensa relocation qualification

This additive draft is stacked above unchanged Wave PR26 exact head
`30ef8d4fbe7bf63072c72988e3711880672d1196`. It does not replace PR26's
complete product admission or the existing accepted baseline and failures.

The harness executes the pinned Runtime's production `esp_elf.c`, validator,
`arch/esp_elf_xtensa.c`, complete adapter, reader-instance/dlmod ownership,
and ordinary privilege-scope hooks on a Linux host. It never calls Xtensa
entry points or exports. Mappings have read/write permission, not execute.
SDK heap calls, RTOS primitives and cache publication operations are modeled;
production relocation, remapping arithmetic and cleanup are not replaced.

Inputs are the independently hash-verified released 0.1.29 and candidate
0.1.31 BLE Buttons ELFs. Import addresses come from the actual .64 native ELF
public-export tables via the pinned `verify_update_elf.public_exports`.
The complete released sdkconfig header and SDK 6.1.0 address-range constants
are verified. CACHE_OFFSET, LOAD_PSRAM, ESP32S3, BUS_ADDRESS_MIRROR and dynamic
objects are enabled exactly as released, with SET_MMU absent.

A separate Python ELF parser constructs a byte-for-byte relocated-section
oracle without calling the production mapping functions. It checks every
loaded byte, relocation word, section placement, entry and export address.
The reader creates independently owned fresh snapshots. Production BSS
zeroing is tested against poison-filled allocations; simultaneous independent
instances and repeated loads are checked. Allocation failures, each missing
import, actual unmappable RELATIVE values and cache-backend failures must
leave no owned mappings or module handles.

This is host execution of production relocation code, not target execution.
It does not establish target allocator fit, instruction execution, installation,
BLE/radio behavior or physical acceptance. Input bytes plus mapped sections
exclude loader objects, symbol/name storage and allocator overhead; host
pointer sizes differ from the target. The low-address allocator is not an
ESP32 allocator-capacity simulation.

## Run

Use the unchanged PR26 baseline, Runtime, image-helper and Utilities PR98
candidate archive inputs. Fetch `soc.h` and `esp_idf_version.h` from SDK commit
`fff9895c82d744c7237be8847347bdd1b07c6643` into a separate SDK-header directory.
Install pyelftools 0.32. Run from a clean committed checkout:

```sh
python scripts/qualify_t039_xtensa_relocations.py \
  --baseline .source/release --runtime .source/runtime \
  --image-helper .source/image-helper --utilities-archive .source/utilities-pr98.zip \
  --sdk-headers .source/sdk-headers --output dist/t039-xtensa-relocation
```

The receipt records passed/failed state and exact source. Initial publication
is source-only until exact-head CI has completed. No merge, release, tags,
firmware publication, device/radio actions or policy widening is authorized.
