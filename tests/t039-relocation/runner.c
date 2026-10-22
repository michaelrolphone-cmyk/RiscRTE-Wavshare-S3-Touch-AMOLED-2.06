/* Host execution of unchanged production loader and Xtensa relocation code.
 * No target entry or export is called. All mappings are non-executable.
 * The SDK heap, RTOS primitives and cache operations are explicit models. */
#include <assert.h>
#include <errno.h>
#include <inttypes.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <unistd.h>
#include "esp_elf.h"
#include "esp_dlfcn.h"
#include "private/esp_dlmod.h"
#include "private/elf_platform.h"
#include "private/esp_privileged_os_cpu.h"
#include "freertos/task.h"
#include "esp_heap_caps.h"
#include "soc/soc.h"
#include "released_exports.h"

extern bool esp_elf_validate_file(const uint8_t *, size_t);
struct allocation { void *pointer; size_t requested, mapped; };
static struct allocation blocks[4096];
static unsigned live, calls, fail_at, fail_cache, cache_writes, cache_invalidates;
static unsigned snapshots, peak_live;
static size_t live_bytes, peak_bytes;
static int relocation_result;
static TickType_t ticks;
static const char *missing;
static uintptr_t pending_cache;
static size_t pending_cache_size;
static const char *output;

/* First-fit mappings in the released S3 D-bus range, with a guard page after
 * each allocation. This models addresses, not a physical allocator or fit. */
void *heap_caps_malloc(size_t size, unsigned caps) {
    assert(size && caps == (MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT));
    if (++calls == fail_at) return NULL;
    const size_t mapped = (size + 4095u) & ~4095u;
    assert(mapped <= SOC_DROM_HIGH - SOC_DROM_LOW - 8192u);
    void *p = MAP_FAILED;
    for (uintptr_t at = SOC_DROM_LOW + 0x10000; at + mapped + 4096 < SOC_DROM_HIGH; at += 4096) {
        int overlap = 0;
        for (unsigned i = 0; i < 4096; ++i)
            if (blocks[i].pointer && at < (uintptr_t)blocks[i].pointer + blocks[i].mapped + 4096 &&
                (uintptr_t)blocks[i].pointer < at + mapped + 4096) { overlap = 1; break; }
        if (overlap) continue;
        p = mmap((void *)at, mapped, PROT_READ | PROT_WRITE,
                 MAP_PRIVATE | MAP_ANONYMOUS | MAP_FIXED_NOREPLACE, -1, 0);
        if (p != MAP_FAILED) break;
        assert(errno == EEXIST); /* Unsupported/unavailable addressing is a failure. */
    }
    assert(p != MAP_FAILED && (uintptr_t)p + mapped <= UINT32_MAX);
    for (unsigned i = 0; i < 4096; ++i) if (!blocks[i].pointer) {
        blocks[i] = (struct allocation){p, size, mapped};
        ++live; live_bytes += size;
        if (live > peak_live) peak_live = live;
        if (live_bytes > peak_bytes) peak_bytes = live_bytes;
        memset(p, 0xa5, mapped); /* BSS must be zeroed by production, not allocator. */
        return p;
    }
    abort();
}
void heap_caps_free(void *p) {
    if (!p) return;
    for (unsigned i = 0; i < 4096; ++i) if (blocks[i].pointer == p) {
        assert(live && live_bytes >= blocks[i].requested);
        --live; live_bytes -= blocks[i].requested;
        assert(munmap(p, blocks[i].mapped) == 0);
        memset(&blocks[i], 0, sizeof(blocks[i])); return;
    }
    abort(); /* Includes duplicate frees and foreign pointers. */
}
static size_t request_size(const void *p) {
    for (unsigned i = 0; i < 4096; ++i) if (blocks[i].pointer == p) return blocks[i].requested;
    abort();
}
TickType_t xTaskGetTickCount(void) { return ticks; }
void vTaskDelay(TickType_t n) { ticks += n; }
TaskHandle_t xTaskGetCurrentTaskHandle(void) { return (void *)&ticks; }
int Cache_WriteBack_Addr(uint32_t address, uint32_t size) {
    assert(address >= SOC_DROM_LOW && address + size <= SOC_DROM_HIGH && size && size <= 4096);
    ++cache_writes; pending_cache = address; pending_cache_size = size;
    return fail_cache == 1 ? -1 : 0;
}
int Cache_Invalidate_Addr(uint32_t address, uint32_t size) {
    assert(address == pending_cache + SOC_IROM_LOW - SOC_DROM_LOW && size == pending_cache_size);
    ++cache_invalidates; return fail_cache == 2 ? -1 : 0;
}
void risc_perf_loader_event(uint32_t phase, uint32_t value) {
    if (phase == 43) relocation_result = (int32_t)value;
}
void esp_elf_registered_symbol_used(const void *table, const char *name, uintptr_t address) {
    (void)table; (void)name; (void)address;
}
uintptr_t elf_find_sym_default(const char *name) {
    if (missing && !strcmp(missing, name)) return 0;
    for (unsigned i = 0; i < sizeof(released_exports)/sizeof(released_exports[0]); ++i)
        if (!strcmp(released_exports[i].name, name)) return released_exports[i].address;
    return 0;
}
struct input { uint8_t *data; size_t size; };
static int snapshot(void *context, const char *path, elf_file_t *file) {
    (void)path; struct input *source = context; ++snapshots;
    uint8_t *copy = esp_elf_malloc(source->size, false);
    if (!copy) { errno = ENOMEM; return -1; }
    memcpy(copy, source->data, source->size);
    if (!esp_elf_validate_file(copy, source->size)) { esp_elf_free(copy); errno = EINVAL; return -1; }
    file->payload = copy; file->size = source->size; return 0;
}
static struct dlmod_slist_t *open_instance(struct input *source) {
    relocation_result = INT32_MIN;
    return esp_dlopen_reader_instance("/sd/Apps/ble_buttons/ble_buttons.elf", snapshot, source);
}
static void empty(void) {
    assert(!live && !live_bytes && !dlmod_gethandle("ble_buttons"));
    assert(!esp_elf_privileged_os_cpu_scope_owned_v1());
}
static void dump(struct dlmod_slist_t *mod, const char *label) {
    assert(dlmod_validate_handle(mod));
    char path[1024]; snprintf(path, sizeof(path), "%s/%s.json", output, label);
    FILE *f = fopen(path, "w"); assert(f);
    esp_elf_t *elf = mod->elf;
    fprintf(f, "{\"entry\":%" PRIuPTR ",\"ptext\":%" PRIuPTR ",\"pdata\":%" PRIuPTR
            ",\"text_request\":%zu,\"data_request\":%zu,\"sections\":[",
            (uintptr_t)elf->entry, (uintptr_t)elf->ptext, (uintptr_t)elf->pdata,
            request_size(elf->ptext), request_size(elf->pdata));
    for (unsigned i = 0; i < ELF_SECS; ++i) {
        esp_elf_sec_t *s = &elf->sec[i];
        assert(!s->size || (s->addr >= SOC_DROM_LOW && s->addr + s->size <= SOC_DROM_HIGH));
        fprintf(f, "%s{\"slot\":%u,\"virtual\":%" PRIuPTR ",\"address\":%" PRIuPTR
                ",\"size\":%zu,\"offset\":%jd}", i ? "," : "", i, s->v_addr, s->addr, s->size, (intmax_t)s->offset);
        snprintf(path, sizeof(path), "%s/%s-%u.bin", output, label, i);
        FILE *b = fopen(path, "wb"); assert(b);
        assert(fwrite((void *)s->addr, 1, s->size, b) == s->size); assert(!fclose(b));
    }
    fprintf(f, "],\"exports\":{");
    for (unsigned i = 0; i < elf->num; ++i) {
        assert(dlsym(mod, elf->symtab[i].name) == elf->symtab[i].addr);
        fprintf(f, "%s\"%s\":%" PRIuPTR, i ? "," : "", elf->symtab[i].name, (uintptr_t)elf->symtab[i].addr);
    }
    fprintf(f, "}}\n"); assert(!fclose(f));
}
static void failed(struct input *source, int expected) {
    assert(!open_instance(source));
    if (expected != INT32_MIN) assert(relocation_result == expected);
    empty();
}
int main(int argc, char **argv) {
    assert(argc == 3); output = argv[2];
    FILE *f = fopen(argv[1], "rb"); assert(f); assert(!fseek(f, 0, SEEK_END));
    long length = ftell(f); assert(length > 52); rewind(f);
    struct input source = {malloc(length), (size_t)length}; assert(source.data);
    assert(fread(source.data, 1, source.size, f) == source.size); assert(!fclose(f));
    assert(esp_elf_validate_file(source.data, source.size));
    empty();
    struct dlmod_slist_t *first = open_instance(&source); assert(first && !relocation_result);
    unsigned success_calls = calls; dump(first, "first");
    assert(cache_writes && cache_writes == cache_invalidates);
    memset((void *)first->elf->sec[ELF_SEC_BSS].addr, 0x6c, first->elf->sec[ELF_SEC_BSS].size);
    memset((void *)first->elf->sec[ELF_SEC_DATA].addr, 0x6d, first->elf->sec[ELF_SEC_DATA].size);
    struct dlmod_slist_t *second = open_instance(&source); assert(second && second != first);
    assert(second->elf != first->elf && second->elf->ptext != first->elf->ptext && second->elf->pdata != first->elf->pdata);
    dump(second, "second");
    for (size_t i = 0; i < first->elf->sec[ELF_SEC_BSS].size; ++i)
        assert(((uint8_t *)first->elf->sec[ELF_SEC_BSS].addr)[i] == 0x6c);
    assert(!dlclose(first)); assert(!dlmod_validate_handle(first));
    dump(second, "second-after-close"); assert(!dlclose(second)); empty();
    struct dlmod_slist_t *again = open_instance(&source); assert(again); dump(again, "reloaded");
    assert(!dlclose(again)); empty();
    unsigned allocation_failures = 0;
    for (unsigned i = 1; i <= success_calls; ++i) {
        calls = 0; fail_at = i; failed(&source, INT32_MIN); ++allocation_failures;
    }
    fail_at = 0;
    unsigned import_failures = 0;
    for (unsigned i = 0; i < sizeof(required_imports)/sizeof(required_imports[0]); ++i) {
        missing = required_imports[i]; failed(&source, -ENOSYS); ++import_failures;
    }
    missing = NULL;
    /* A structurally valid image with an unmappable RELATIVE word must fail
     * in actual Xtensa relocation, not an injected architecture return value. */
    elf32_hdr_t *header = (void *)source.data;
    elf32_shdr_t *sections = (void *)(source.data + header->shoff);
    uint32_t *relative_word = NULL;
    for (unsigned i = 0; i < header->shnum && !relative_word; ++i) if (sections[i].type == SHT_RELA) {
        elf32_rela_t *rows = (void *)(source.data + sections[i].offset);
        for (unsigned j = 0; j < sections[i].size / sizeof(*rows) && !relative_word; ++j) if (ELF_R_TYPE(rows[j].info) == 5)
            for (unsigned k = 0; k < header->shnum; ++k) if ((sections[k].flags & SHF_ALLOC) && sections[k].type == SHT_PROGBITS &&
                    rows[j].offset >= sections[k].addr && rows[j].offset + 4 <= sections[k].addr + sections[k].size)
                relative_word = (void *)(source.data + sections[k].offset + rows[j].offset - sections[k].addr);
    }
    assert(relative_word); uint32_t original = *relative_word;
    const uint32_t invalid_targets[] = {0x60000000u, 0x600fe000u, 0xffffffffu};
    for (unsigned i = 0; i < 3; ++i) {
        *relative_word = invalid_targets[i]; assert(esp_elf_validate_file(source.data, source.size));
        unsigned before = cache_writes; failed(&source, -EINVAL); assert(cache_writes == before);
    }
    *relative_word = original;
    for (fail_cache = 1; fail_cache <= 2; ++fail_cache) failed(&source, -EIO);
    fail_cache = 0;
    again = open_instance(&source); assert(again); dump(again, "after-failures"); assert(!dlclose(again)); empty();
    char path[1024]; snprintf(path, sizeof(path), "%s/controls.json", output); f = fopen(path, "w"); assert(f);
    fprintf(f, "{\"allocation_failures\":%u,\"missing_import_failures\":%u,\"real_relocation_failures\":3,"
            "\"cache_backend_failures\":2,\"snapshots\":%u,\"peak_host_requested_bytes\":%zu,"
            "\"peak_live_allocations\":%u,\"host_pointer_bytes\":%zu,\"remaining_allocations\":%u,"
            "\"target_instructions_executed\":false}\n", allocation_failures, import_failures, snapshots,
            peak_bytes, peak_live, sizeof(void *), live);
    assert(!fclose(f)); free(source.data);
    puts("PASS: production Xtensa relocation, reader ownership, fresh independent instances and all cleanup controls");
    return 0;
}
