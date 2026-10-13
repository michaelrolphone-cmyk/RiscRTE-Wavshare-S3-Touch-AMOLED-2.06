#include "../src/Phase.h"
#include <cassert>
#include <cstdio>
int main(){
    for(uint32_t p=0;p<4;p++){
        assert(link_phase(true,p,LINK_PHASE_MAGIC^p)==p);
        assert(link_phase(false,p,LINK_PHASE_MAGIC^p)==0);
        assert(link_phase(true,p,(LINK_PHASE_MAGIC^p)^8)==0);
        uint32_t next=(p+1)%4;assert(link_phase(true,next,LINK_PHASE_MAGIC^next)==next);
    }
    assert(link_phase(true,4,LINK_PHASE_MAGIC^4)==0);
    assert(link_phase(true,UINT32_MAX,LINK_PHASE_MAGIC^UINT32_MAX)==0);
    puts("Display-link phase selection: cold boot, restart, cookie corruption and four-stage cycle PASS");
}
