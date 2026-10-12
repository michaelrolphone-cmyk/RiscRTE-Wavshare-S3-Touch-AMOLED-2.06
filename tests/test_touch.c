#include "hardware_model.h"
#include "../drivers/touch_ft3168/driver.c"
static void config_(void) {
    static risc_hw_i2c_touch_v1 device;
    device=(risc_hw_i2c_touch_v1){.struct_size=sizeof(device),.bus=i2c_config_,.address=0x38,.width=410,.height=502,.irq=38,.reset=9,.reset_assert_ms=10,.reset_recovery_ms=120};
    hardware_.compatible="focaltech,ft3168";hardware_.config_type="touch.i2c";hardware_.config=&device;hardware_.config_size=sizeof(device);
}
static void contact_(unsigned index,uint8_t id,unsigned x,unsigned y) {
    uint8_t *p=registers_+3+index*6;p[0]=(x>>8)&15;p[1]=x;p[2]=(id<<4)|((y>>8)&15);p[3]=y;
}
int main(void) {
    config_();reset_model_();const risc_driver_v2 *d=t5_driver_get(2);const risc_touch_api_v1 *a=d->capability;
    assert(d->start(deps_,4));assert(tick_==130 && pin_levels_[9]);
    uint64_t sub=a->subscribe(NULL);assert(sub);risc_touch_event_v1 e={0};risc_touch_snapshot_v1 s={0};
    registers_[2]=1;contact_(0,2,409,501);assert(a->poll(NULL,1));assert(a->next(NULL,sub,&e)==1 && e.kind==RISC_TOUCH_EVENT_DOWN && e.x==409 && e.y==501);
    assert(a->snapshot(NULL,&s) && s.width==410 && s.height==502 && s.sequence==e.sequence);
    assert(a->poll(NULL,1));assert(a->next(NULL,sub,&e)==0);
    contact_(0,3,205,251);assert(a->poll(NULL,1));assert(a->next(NULL,sub,&e)==1 && e.kind==RISC_TOUCH_EVENT_UP && e.id==2);
    assert(a->next(NULL,sub,&e)==1 && e.kind==RISC_TOUCH_EVENT_DOWN && e.id==3);
    registers_[2]=2;contact_(0,3,20,30);contact_(1,8,40,50);assert(a->poll(NULL,1));
    while(a->next(NULL,sub,&e)>0){} assert(a->snapshot(NULL,&s) && s.contact_count==2);
    registers_[2]=0;assert(a->poll(NULL,1));assert(a->next(NULL,sub,&e)==1 && e.kind==RISC_TOUCH_EVENT_UP);assert(a->next(NULL,sub,&e)==1 && e.kind==RISC_TOUCH_EVENT_UP);
    registers_[2]=3;assert(!a->poll(NULL,1));assert(a->next(NULL,sub,&e)==-1);
    assert(!d->quiesce());assert(a->unsubscribe(NULL,sub));assert(d->quiesce());no_claims_();
    for(unsigned n=1;n<=2;n++) {reset_model_();fail_gpio_=n;assert(!d->start(deps_,4));assert(d->quiesce());no_claims_();}
    reset_model_();fail_transaction_=1;assert(!d->start(deps_,4));assert(d->quiesce());no_claims_();
    puts("FT3168 touch: 410x502 coordinates, reset, replacement order, multi-touch, gaps and cleanup PASS");
}
