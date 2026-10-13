#include "hardware_model.h"
#include "provider_log_mock.h"
#include "../drivers/display_rail_axp2101/driver.c"
static const risc_provider_dependency_v1 supply_deps[]={{"i2c.bus",1,&bus_},{"platform.clock",1,&clock_}};
static bool fail_release,ignore_write;
static bool release_fault(void *c,uint64_t token) {
 if(fail_release)return false;
 return bus_release_(c,token);
}
static bool transact_fault(void *c,uint64_t token,const uint8_t *tx,size_t n,uint8_t *rx,size_t rn,uint32_t ms) {
 if(ignore_write && !rn){transactions_++;return true;}
 return transact_(c,token,tx,n,rx,rn,ms);
}
static void setup(void) {
 (void)deps_;(void)i2c_config_;
 stop();no_claims_();reset_model_();diagnostics_[0]=0;
 bus_.release_device=release_fault;bus_.transact=transact_fault;
 fail_release=ignore_write=false;
 for(unsigned i=0;i<256;i++)registers_[i]=(uint8_t)(i^0xa5);
 registers_[3]=0x4a;registers_[0x90]=0xb5;registers_[0x93]=0xe4;
}
int main(void) {
 setup();uint8_t initial[256];memcpy(initial,registers_,256);
 assert(start(supply_deps,2)&&!bus_token_&&!writes_); /* probe must not turn rail on */
 risc_power_rail_info_v1 state={.struct_size=sizeof(state)};
 assert(get_info(NULL,&state)&&!state.enabled&&state.configured_millivolts==900);
 assert(set_enabled(NULL,true)&&!bus_token_);
 assert(registers_[0x90]==0xb7&&registers_[0x93]==0xfc);
 assert(writes_==2&&write_registers_[0]==0x93&&write_registers_[1]==0x90);
 assert(strstr(diagnostics_,"stage=before aldo2_enabled=0 configured_mv=900"));
 assert(strstr(diagnostics_,"stage=after aldo2_enabled=1 configured_mv=3300"));
 for(unsigned i=0;i<256;i++)if(i!=0x90&&i!=0x93)assert(registers_[i]==initial[i]);
 assert(get_info(NULL,&state)&&state.enabled&&state.configuration_verified&&state.configured_millivolts==3300);
 unsigned previous=writes_;assert(set_enabled(NULL,true)&&writes_==previous); /* already correct: no write */
 assert(set_enabled(NULL,false)&&registers_[0x90]==0xb5&&registers_[0x93]==0xfc);
 assert(quiesce());stop();no_claims_();
 setup();registers_[0x90]|=2;assert(start(supply_deps,2));assert(set_enabled(NULL,true));
 assert(writes_==3&&write_registers_[0]==0x90&&write_registers_[1]==0x93&&write_registers_[2]==0x90);
 assert(registers_[0x90]==0xb7&&registers_[0x93]==0xfc);stop();
 for(unsigned failure=1;failure<=3;failure++) {
  setup();fail_transaction_=failure;assert(!start(supply_deps,2));assert(quiesce());no_claims_();
 }
 setup();registers_[3]=0;assert(!start(supply_deps,2));assert(!writes_);no_claims_();
 setup();assert(start(supply_deps,2));unsigned first=transactions_;assert(set_enabled(NULL,true));unsigned count=transactions_-first;stop();
 for(unsigned failure=1;failure<=count;failure++) {
  setup();assert(start(supply_deps,2));fail_transaction_=transactions_+failure;
  assert(!set_enabled(NULL,true));assert(!bus_token_);stop();no_claims_();
 }
 setup();assert(start(supply_deps,2));ignore_write=true;assert(!set_enabled(NULL,true));ignore_write=false;stop();
 setup();assert(start(supply_deps,2));fail_release=true;assert(!set_enabled(NULL,true));
 assert(session&&!quiesce());assert(!get_info(NULL,&state));fail_release=false;assert(quiesce());stop();no_claims_();
 setup();assert(start(supply_deps,2));uint64_t foreign=0;assert(bus_claim_(NULL,0x34,&foreign));
 assert(!set_enabled(NULL,true));assert(!writes_);assert(bus_release_(NULL,foreign));
 assert(set_enabled(NULL,true));stop();no_claims_();
 puts("Power rail: cold-off/incorrect-voltage/already-on states, exact masked writes, unrelated-register preservation, readback failures and retained claims PASS");
}
