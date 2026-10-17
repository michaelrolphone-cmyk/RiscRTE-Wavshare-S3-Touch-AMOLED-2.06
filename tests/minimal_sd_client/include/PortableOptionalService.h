#pragma once
#include "RiscRuntimeV1.h"
/* Absence is qualified only at acquisition, never inferred from a null API
 * after validation, a partial grant, or revoked invocation authority. */
static inline bool portable_optional_grant_owned(const risc_runtime_capability_v1 *g) {
    return g->api || g->slot || g->generation;
}
static inline bool portable_optional_missing(const risc_runtime_api_v1 *rt,
        const risc_runtime_capability_v1 *grant) {
    if(grant->struct_size!=sizeof(*grant) || portable_optional_grant_owned(grant))return false;
    risc_runtime_health_v1 health={.struct_size=sizeof(health)};
    return rt->health&&rt->health(&health);
}
static inline bool portable_optional_acquire(const risc_runtime_api_v1 *rt,
        const char *name,risc_runtime_capability_v1 *grant,bool *unavailable,bool *uncertain) {
    *unavailable=*uncertain=false;
    if(rt->acquire(name,1,0,grant))return true;
    if(!portable_optional_missing(rt,grant)){*uncertain=true;return false;}
    *unavailable=true;return false;
}

#include "RiscKeyValueV1.h"
/* Synchronous checked forwarding preserves CONTEXT through legacy bool
 * preference helpers. The first revoked access suppresses all later callbacks
 * and release; the adapter terminally retains the original grant. */
typedef struct {
    risc_key_value_v1 api;
    const risc_key_value_v1 *provider;
    bool *uncertain;
} portable_optional_kv;
static inline int32_t portable_optional_kv_get(void *context,const char *key,
        void *bytes,uint32_t capacity,uint32_t *size) {
    portable_optional_kv *g=context;
    if(*g->uncertain){if(size)*size=0;return RISC_KEY_VALUE_CONTEXT;}
    int32_t result=g->provider->get(g->provider->context,key,bytes,capacity,size);
    if(result==RISC_KEY_VALUE_CONTEXT)*g->uncertain=true;
    return result;
}
static inline int32_t portable_optional_kv_put(void *context,const char *key,
        const void *bytes,uint32_t size) {
    portable_optional_kv *g=context;
    if(*g->uncertain)return RISC_KEY_VALUE_CONTEXT;
    int32_t result=g->provider->put(g->provider->context,key,bytes,size);
    if(result==RISC_KEY_VALUE_CONTEXT)*g->uncertain=true;
    return result;
}
static inline const risc_key_value_v1 *portable_optional_kv_open(portable_optional_kv *g,
        const void *provider,bool *uncertain) {
    const risc_key_value_v1 *kv=provider;
    if(!kv||kv->api_version!=1||kv->struct_size<sizeof(*kv)||!kv->get||!kv->put)return NULL;
    *g=(portable_optional_kv){.api={1,sizeof(g->api),g,portable_optional_kv_get,portable_optional_kv_put},
        .provider=kv,.uncertain=uncertain};
    return &g->api;
}
