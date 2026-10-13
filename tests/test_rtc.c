#include "hardware_model.h"
#include "provider_log_mock.h"
#include "../drivers/rtc_pcf85063/driver.c"
static void config_(void) {
    static tw_hw_i2c_device_v1 device;
    device=(tw_hw_i2c_device_v1){.struct_size=sizeof(device),.bus=i2c_config_,.address=0x51,.irq=39,.irq_pull_up=1};
    hardware_.compatible="nxp,pcf85063a";hardware_.config_type="peripheral.i2c";hardware_.config=&device;hardware_.config_size=sizeof(device);
}
int main(void) {
    config_();reset_model_();registers_[0]=0x22;registers_[1]=0xc7;
    const risc_driver_v2 *d=t5_driver_get(2);assert(d && !t5_driver_get(1));
    const twatch_rtc_api_v1 *a=d->capability;
    assert(d->start(deps_,4));assert(registers_[0]==0 && registers_[1]==0xc7);
    twatch_rtc_time_v1 time={2028,2,29,2,23,59,58},got={0};
    assert(a->write(NULL,&time));assert(registers_[4]==0x58 && registers_[10]==0x28);
    assert(strstr(diagnostics_,"write=transfer-ok raw04_0a=58,59,23,29,02,02,28"));
    assert(a->read(NULL,&got));assert(memcmp(&got,&time,sizeof(time))==0);
    assert(strstr(diagnostics_,"read=valid-calendar"));
    size_t logged=strlen(diagnostics_);assert(a->read(NULL,&got));assert(strlen(diagnostics_)==logged);
    time.year=2027;assert(!a->write(NULL,&time));
    registers_[4]|=0x80;got.year=1111;assert(!a->read(NULL,&got) && got.year==1111);registers_[4]&=0x7f;
    assert(strstr(diagnostics_,"read=oscillator-stop"));
    registers_[5]=0x6a;assert(!a->read(NULL,&got));registers_[5]=0x59;
    assert(strstr(diagnostics_,"read=invalid-bcd"));
    registers_[9]=0;assert(!a->read(NULL,&got));assert(strstr(diagnostics_,"read=invalid-calendar"));registers_[9]=2;
    assert(a->alarm(NULL,34,12,255,2,true));assert(registers_[11]==0 && registers_[12]==0x34 && registers_[13]==0x12 && registers_[14]==0x80 && registers_[15]==2);
    assert(registers_[1]==0x87);bool pending=false;registers_[1]|=0x40;
    assert(a->alarm_pending(NULL,&pending,false) && pending && registers_[1]==0xc7);
    assert(a->alarm_pending(NULL,&pending,true) && pending && registers_[1]==0x87);
    assert(!a->alarm(NULL,60,0,1,0,true));
    assert(a->alarm(NULL,255,255,255,255,false));assert(registers_[1]==7);
    assert(d->quiesce());no_claims_();
    for(unsigned n=1;n<=2;n++) {reset_model_();fail_transaction_=n;assert(!d->start(deps_,4));assert(d->quiesce());no_claims_();}
    reset_model_();fail_gpio_=1;assert(!d->start(deps_,4));assert(d->quiesce());no_claims_();
    reset_model_();assert(d->start(deps_,4));fail_transaction_=transactions_+1;assert(!a->read(NULL,&got));
    assert(strstr(diagnostics_,"read=transfer-failed"));
    time.year=2028;fail_transaction_=transactions_+1;assert(!a->write(NULL,&time));
    assert(strstr(diagnostics_,"write=transfer-failed"));
    fail_transaction_=0;assert(a->write(NULL,&time));assert(a->read(NULL,&got));
    assert(d->quiesce());assert(d->start(deps_,4));assert(a->read(NULL,&got));assert(memcmp(&got,&time,sizeof(time))==0);
    assert(d->quiesce());no_claims_();
    puts("PCF85063 RTC: time, leap-year, oscillator flag, BCD, alarms and cleanup PASS");
}
