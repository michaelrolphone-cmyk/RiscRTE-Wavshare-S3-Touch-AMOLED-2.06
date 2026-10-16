/* Production Wave SD/FatFs + shared MSC/TinyUSB, modeled DCD/native media. */
#define main owner_fixture_main
#include "owner_test.c"
#undef main
extern const risc_storage_volume_api_v1_export_prepare *wave_test_start(void);
extern void wave_test_frozen(void),wave_test_finish(void);
static const risc_storage_volume_api_v1_export_prepare *wave;
static int32_t begin_wave(void*c,uint64_t*t){int32_t r=wave->begin_prepare(c,t);assert(r==2);sd_owned=true;mark('M');return r;}
static int32_t end_wave(void*c,uint64_t t){assert(!usb_live);int32_t r=wave->base.export_end(c,t);assert(!r);sd_owned=false;mark('E');return r;}
static void transfer(bool read,uint8_t*b,unsigned sectors){
 command(read?0x28:0x2a,sectors*512,read,9000,sectors,0);
 for(unsigned done=0;done<sectors*512;){
  unsigned dir=read?1:0;unsigned n=ep[1][dir].length;
  assert(ep[1][dir].pending&&n&&n<=4096&&n<=sectors*512-done);
  if(read)memcpy(b+done,ep[1][1].buffer,n);
  complete(read?0x81:1,read?NULL:b+done,n);assert(poll()==0);done+=n;
 }
 assert(csw(true)==0);
}
int main(int argc,char**argv){
 assert(argc==2);wave=wave_test_start();assert(wave);
 volume=*wave;volume.begin_prepare=begin_wave;volume.base.export_end=end_wave;
 connect_provider();configure();wave_test_frozen();
 uint8_t original[65536],pattern[65536],copy[65536];
 transfer(true,original,128);for(unsigned i=0;i<sizeof(pattern);++i)pattern[i]=(uint8_t)(i*23+7);
 const unsigned sizes[]={1,2,7,8,9,15,17,128};
 for(unsigned i=0;i<sizeof(sizes)/sizeof(*sizes);++i){unsigned n=sizes[i];transfer(false,pattern,n);transfer(true,copy,n);assert(!memcmp(copy,pattern,n*512));}
 transfer(false,original,128);transfer(true,copy,128);assert(!memcmp(copy,original,sizeof(copy)));
 if(!strcmp(argv[1],"eject")){
  command(0x1b,0,false,0,0,2);assert(csw(false)==0&&sd_owned&&phy_owned&&usb_live);wave_test_frozen();
  assert(csw(true)==0);assert(poll()==0&&status.state==RISC_USB_MSC_EJECTED);
 }else{assert(!strcmp(argv[1],"disconnect"));dcd_event_bus_signal(0,DCD_EVENT_UNPLUGGED,false);assert(poll()==0&&status.state==RISC_USB_MSC_DISCONNECTED);}
 assert(!sd_owned&&!phy_owned&&!usb_live&&strstr(trace,"TER"));
 assert(api->end(NULL,token,RISC_USB_MSC_END_CANCEL_WAITING)==0);assert(t5_driver_get(2)->quiesce());
 wave_test_finish();puts("Actual Wave SD + MSC/TinyUSB: multiblock exact data, restore, checked USB stop/remount/PHY release PASS");
}
