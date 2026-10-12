#include "hardware_model.h"
static bool command_stuck,wake_enrolled;
static unsigned handshake_count, status_reads;
static int32_t wake_result;
static bool qmi_transfer(void *c,uint64_t claim,const uint8_t *tx,size_t n,uint8_t *rx,size_t rn,uint32_t ms) {
    if(!transact_(c,claim,tx,n,rx,rn,ms))return false;
    if(rn&&tx[0]<=0x2f&&tx[0]+rn>0x2f){status_reads++;pin_levels_[21]=false;registers_[0x2f]=0;}
    if(!rn&&tx[0]==0x0a&&!command_stuck){registers_[0x2d]=tx[1]?0x80:0;handshake_count++;}
    return true;
}
static int32_t wake_source_(void *c,uint64_t token,bool high,uint32_t modes) {
    (void)c;assert(token==22&&pins_[21]&&high&&(modes==0||modes==3));
    if(wake_result)return wake_result;
    wake_enrolled=modes!=0;return 0;
}
#include "../drivers/motion_qmi8658/driver.c"
static void setup(void) {
    reset_model_();assert(!wake_enrolled);command_stuck=false;wake_result=0;handshake_count=status_reads=0;
    static tw_hw_i2c_device_v1 device;
    device=(tw_hw_i2c_device_v1){.struct_size=sizeof(device),.bus=i2c_config_,.address=0x6b,.chip_id=5,.irq=21,.irq_active_high=1};
    hardware_.compatible="qst,qmi8658c";hardware_.config_type="peripheral.i2c";hardware_.config=&device;hardware_.config_size=sizeof(device);
    bus_.transact=qmi_transfer;gpio_.wake_source=wake_source_;registers_[0]=5;
}
int main(void) {
    setup();assert(start(deps_,4));assert(registers_[3]==0x16&&registers_[8]==0x21);
    registers_[0x35]=0;registers_[0x36]=0x20;registers_[0x37]=0;registers_[0x38]=0xe0;registers_[0x39]=0xff;registers_[0x3a]=0x7f;
    twatch_accel_sample_v1 value={0};assert(sample(NULL,&value)&&value.x==1000&&value.y==-1000&&value.z==3999);
    uint8_t id=0;assert(chip_id(NULL,&id)&&id==5);
    twatch_tap_info_v1 info;assert(tap_info(NULL,&info)&&info.profile==3&&info.default_value==800);
    assert(!tap_configure(NULL,99)&&!tap_configure(NULL,4001)&&tap_configure(NULL,1500));
    assert(prepare_wake(NULL)&&wake_enrolled&&handshake_count==4);
    assert(registers_[0x0d]==(1500&255)&&registers_[0x0e]==(1500>>8)&&registers_[3]==0x14&&registers_[2]==0x48);
    assert(!sample(NULL,&value)&&!tap_configure(NULL,1000));
    bool pending=false;pin_levels_[21]=true;registers_[0x2f]=2;unsigned before=status_reads;
    assert(wake_pending(NULL,&pending)&&pending&&status_reads==before&&registers_[0x2f]==2);
    assert(restore(NULL)&&!wake_enrolled&&registers_[3]==0x16&&registers_[8]==0x21&&registers_[2]==0x40);
    assert(restore(NULL));assert(observe_begin(NULL,800)&&!wake_enrolled);
    registers_[0x2e]=1;registers_[0x2f]=2;registers_[0x59]=2;
    twatch_tap_observation_v1 observed={0};assert(observe(NULL,&observed)&&observed.double_tap&&observed.sample_ready&&observed.x_mg==1000);
    assert(restore(NULL)&&quiesce());no_claims_();
    setup();assert(start(deps_,4));command_stuck=true;assert(!prepare_wake(NULL)&&tick_<=220);command_stuck=false;assert(restore(NULL)&&quiesce());
    /* Every configuration I/O failure still permits explicit rollback. */
    setup();assert(start(deps_,4));unsigned first=transactions_;assert(prepare_wake(NULL));unsigned count=transactions_-first;assert(restore(NULL)&&quiesce());
    for(unsigned n=1;n<=count;n++) {
        setup();assert(start(deps_,4));fail_transaction_=transactions_+n;
        assert(!prepare_wake(NULL));fail_transaction_=0;assert(restore(NULL)&&quiesce());no_claims_();
    }
    setup();registers_[0]=0;assert(!start(deps_,4));assert(quiesce());no_claims_();
    setup();assert(start(deps_,4)&&prepare_wake(NULL));fail_transaction_=transactions_+1;
    assert(!restore(NULL)&&wake_enrolled&&bus_token_);fail_transaction_=0;assert(restore(NULL)&&quiesce());
    setup();assert(start(deps_,4));wake_result=RISC_LIGHT_SLEEP_RETAINED;
    assert(!prepare_wake(NULL)&&!restore(NULL)&&!quiesce());
    puts("QMI8658: coherent milli-g, tap protocol, passive wake observation, rollback and retained faults PASS");
}
