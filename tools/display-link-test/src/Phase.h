#pragma once
#include <stdint.h>
constexpr uint32_t LINK_PHASE_MAGIC=0x574c5434;
constexpr uint32_t link_phase(bool resume,uint32_t next,uint32_t check){
    return resume&&next<4&&check==(LINK_PHASE_MAGIC^next)?next:0;
}
