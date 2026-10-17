#pragma once
#include "PortableOptionalService.h"
#include "RiscAppCatalogV1.h"
#include "T5AppApi.h"
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
/* One native publication, copied without granting update or filesystem access.
 * Only rows obtained from the owner are visible. Failed refreshes clear stale
 * rows; ambiguous custody retains both the grant and all client allocations. */
typedef struct {
    t5_app_manifest_t manifest;
    char route[RISC_APP_CATALOG_ROUTE_MAX];
} portable_app_catalog_item;
typedef struct {
    risc_runtime_capability_v1 grant;
    const risc_app_catalog_v1 *api;
    portable_app_catalog_item *entries, *staging;
    uint64_t generation;
    uint32_t count;
    bool initialized, uncertain;
    const char *failure_stage;
    int32_t failure_result;
    uint32_t failure_index;
} portable_app_catalog;
/* Emit only with established custody. CONTEXT/RETAINED must not cause another
 * runtime callback; those cases keep the existing terminal retention fence. */
static inline void portable_catalog_diagnostic(portable_app_catalog *c,const risc_runtime_api_v1 *rt,
        const char *stage,int32_t result,uint32_t index,size_t bytes,uint64_t expected,uint64_t actual) {
    if(c->uncertain)return;
    c->failure_stage=stage;c->failure_result=result;c->failure_index=index;
    if(!rt->diagnostic)return;
    char line[224];
    snprintf(line,sizeof(line),"APP_CATALOG stage=%s result=%ld index=%lu bytes=%lu expected=%llu actual=%llu",
        stage,(long)result,(unsigned long)index,(unsigned long)bytes,
        (unsigned long long)expected,(unsigned long long)actual);
    rt->diagnostic(line);
}
static inline bool portable_catalog_result(portable_app_catalog *c,int32_t result) {
    if(result==RISC_APP_CATALOG_CONTEXT || result==RISC_APP_CATALOG_RETAINED)c->uncertain=true;
    return result==RISC_APP_CATALOG_OK;
}
static inline bool portable_catalog_text(const char *text,size_t capacity,bool required) {
    size_t i=0;
    for(;i<capacity && text[i];i++)if((unsigned char)text[i]<32 || (unsigned char)text[i]==127)return false;
    return i<capacity && (!required || i);
}
static inline bool portable_catalog_path(const char *path,size_t capacity) {
    if(!portable_catalog_text(path,capacity,true) || *path=='/')return false;
    const char *part=path;
    for(const char *p=path;;p++) {
        if(*p=='\\' || *p==':')return false;
        if(*p!='/' && *p)continue;
        size_t n=(size_t)(p-part);
        if(!n || (n==1 && part[0]=='.') || (n==2 && part[0]=='.' && part[1]=='.'))return false;
        if(!*p)return true;
        part=p+1;
    }
}
static inline bool portable_catalog_entry(const risc_app_catalog_entry_v1 *entry,portable_app_catalog_item *item) {
    if(entry->struct_size<sizeof(*entry) || (entry->flags&~RISC_APP_CATALOG_AVAILABLE) ||
       !portable_catalog_text(entry->display_name,sizeof(entry->display_name),true) ||
       !portable_catalog_path(entry->file_name,sizeof(entry->file_name)) ||
       !portable_catalog_text(entry->min_firmware_version,sizeof(entry->min_firmware_version),false) ||
       !portable_catalog_text(entry->icon,sizeof(entry->icon),false) ||
       !portable_catalog_text(entry->id,sizeof(entry->id),true))return false;
    memset(item,0,sizeof(*item));
    t5_app_manifest_t *out=&item->manifest;
    memcpy(out->display_name,entry->display_name,sizeof(out->display_name));
    strcpy(item->route,entry->file_name);
    if(strlen(entry->file_name)<sizeof(out->file_name))strcpy(out->file_name,entry->file_name);
    else {strcpy(out->file_name,"id:");strcpy(out->file_name+3,entry->id);}
    memcpy(out->min_firmware_version,entry->min_firmware_version,sizeof(out->min_firmware_version));
    memcpy(out->icon,entry->icon,sizeof(out->icon));
    out->compatible=!!(entry->flags&RISC_APP_CATALOG_AVAILABLE);
    return true;
}
static inline void portable_catalog_clear(portable_app_catalog *c) {
    if(c->uncertain)return;
    free(c->staging);c->staging=NULL;free(c->entries);c->entries=NULL;c->count=0;c->generation=0;
}
static inline bool portable_catalog_close(portable_app_catalog *c,const risc_runtime_api_v1 *rt) {
    if(c->uncertain)return false;
    if(portable_optional_grant_owned(&c->grant)) {
        risc_runtime_capability_v1 owned=c->grant;
        if(!rt->release(&c->grant)){c->grant=owned;c->uncertain=true;return false;}
    }
    portable_catalog_clear(c);memset(c,0,sizeof(*c));return true;
}
static inline bool portable_catalog_open(portable_app_catalog *c,const risc_runtime_api_v1 *rt) {
    if(c->uncertain)return false;
    if(c->api)return true;
    c->grant=(risc_runtime_capability_v1){.struct_size=sizeof(c->grant)};
    bool unavailable=false;
    if(!portable_optional_acquire(rt,RISC_APP_CATALOG_CAPABILITY,&c->grant,&unavailable,&c->uncertain)) {
        portable_catalog_diagnostic(c,rt,"acquire",0,0,0,0,unavailable);return false;
    }
    const risc_app_catalog_v1 *api=c->grant.api;
    if(!api || api->api_version!=1 || api->struct_size<sizeof(*api) || !api->snapshot || !api->get) {
        (void)portable_catalog_close(c,rt);
        portable_catalog_diagnostic(c,rt,"interface",-1,0,0,0,0);return false;
    }
    c->api=api;return true;
}
static inline bool portable_catalog_refresh(portable_app_catalog *c,const risc_runtime_api_v1 *rt) {
    if(c->uncertain)return false;
    c->initialized=true;
    if(!portable_catalog_open(c,rt)){c->initialized=true;portable_catalog_clear(c);return false;}
    risc_app_catalog_snapshot_v1 snapshot={.struct_size=sizeof(snapshot)};
    int32_t result=c->api->snapshot(c->api->context,&snapshot);
    if(!portable_catalog_result(c,result) || snapshot.struct_size<sizeof(snapshot) ||
       !snapshot.generation || snapshot.count>RISC_APP_CATALOG_MAX) {
        portable_catalog_diagnostic(c,rt,"snapshot",result,snapshot.count,snapshot.struct_size,0,snapshot.generation);goto invalid;
    }
    if(snapshot.count) {
        size_t bytes=(size_t)snapshot.count*sizeof(*c->staging);
        c->staging=malloc(bytes);
        if(!c->staging){portable_catalog_diagnostic(c,rt,"allocation-failed",-1,0,bytes,0,0);goto invalid;}
        memset(c->staging,0,(size_t)snapshot.count*sizeof(*c->staging));
        for(uint32_t i=0;i<snapshot.count;i++) {
            risc_app_catalog_entry_v1 entry={.struct_size=sizeof(entry)};
            result=c->api->get(c->api->context,snapshot.generation,i,&entry);
            if(!portable_catalog_result(c,result) || !portable_catalog_entry(&entry,&c->staging[i])) {
                portable_catalog_diagnostic(c,rt,"row",result,i,0,snapshot.generation,0);goto invalid;
            }
            for(uint32_t j=0;j<i;j++)if(!strcmp(c->staging[j].manifest.file_name,c->staging[i].manifest.file_name) ||
                !strcmp(c->staging[j].route,c->staging[i].route)) {
                portable_catalog_diagnostic(c,rt,"duplicate-row",-1,i,0,j,0);goto invalid;
            }
        }
    }
    risc_app_catalog_snapshot_v1 after={.struct_size=sizeof(after)};
    result=c->api->snapshot(c->api->context,&after);
    if(!portable_catalog_result(c,result) || after.struct_size<sizeof(after)) {
        portable_catalog_diagnostic(c,rt,"snapshot-after",result,after.count,after.struct_size,snapshot.generation,after.generation);goto invalid;
    }
    if(after.generation!=snapshot.generation || after.count!=snapshot.count) {
        portable_catalog_diagnostic(c,rt,"generation-mismatch",result,after.count,snapshot.count,snapshot.generation,after.generation);goto invalid;
    }
    free(c->entries);c->entries=c->staging;c->staging=NULL;c->count=snapshot.count;c->generation=snapshot.generation;
    c->failure_stage=NULL;c->failure_result=0;c->failure_index=0;
    return true;
invalid:
    portable_catalog_clear(c);return false;
}
typedef struct {
    uint64_t generation;
    uint32_t index;
    char route[RISC_APP_CATALOG_ROUTE_MAX];
} portable_app_catalog_launch;
static inline bool portable_catalog_launch_valid(portable_app_catalog *c,const portable_app_catalog_launch *launch) {
    if(c->uncertain || !c->api)return false;
    risc_app_catalog_entry_v1 entry={.struct_size=sizeof(entry)};portable_app_catalog_item current;
    if(!portable_catalog_result(c,c->api->get(c->api->context,launch->generation,launch->index,&entry)) ||
       !portable_catalog_entry(&entry,&current)) {portable_catalog_clear(c);return false;}
    if(strcmp(current.route,launch->route)){portable_catalog_clear(c);return false;}
    return current.manifest.compatible;
}
static inline bool portable_catalog_launch_prepare(portable_app_catalog *c,uint32_t index,portable_app_catalog_launch *launch) {
    if(c->uncertain || !c->api || index>=c->count || !c->entries[index].manifest.compatible)return false;
    *launch=(portable_app_catalog_launch){.generation=c->generation,.index=index};
    strcpy(launch->route,c->entries[index].route);
    return portable_catalog_launch_valid(c,launch);
}
