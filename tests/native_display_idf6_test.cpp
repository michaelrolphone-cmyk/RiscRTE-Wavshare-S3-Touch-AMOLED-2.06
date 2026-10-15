// Compile the actual bridge, SDK SPI/GPIO declarations and shared Runtime ABI.
#include "../native/VendorDisplay.cpp"
#include <cassert>
#include <vector>
#include <array>
#include <cstdlib>
#include <algorithm>

struct spi_device_t{};
namespace model {
enum Op { Init,Add,Acquire,Allocate,Configure,Level,Start,End,Remove,Free,Reset,Count };
std::array<unsigned,Count> calls{},failAt{};
esp_err_t endError=ESP_ERR_TIMEOUT;
bool dmaFailure=false,partialAdd=false,bus=false,device=false,acquired=false,flight=false;
int core=0;TaskHandle_t task=reinterpret_cast<TaskHandle_t>(1);
spi_device_t handle;
spi_transaction_t* descriptor=nullptr;
void* allocation=nullptr;
std::array<uint32_t,49> levels{};
std::vector<int> resets;
std::vector<TickType_t> delays;
struct Packet {uint16_t command;uint64_t address;uint32_t flags;std::vector<uint8_t> bytes;bool complete=false;};
std::vector<Packet> packets;
uint64_t clockUs=0;unsigned clockReads=0;
bool failed(Op op){return ++calls[op]==failAt[op];}
void fault(Op op,unsigned after=1){failAt[op]=calls[op]+after;}
void correctOwner(){assert(core==0&&task==reinterpret_cast<TaskHandle_t>(1));}
uint64_t now(){++clockReads;return ++clockUs;}
bool owner(){return true;}
unsigned lit(){return std::count_if(packets.begin(),packets.end(),[](const auto& p){return p.command==2&&p.address==0x5100&&!p.bytes.empty()&&p.bytes[0]!=0;});}
unsigned registerCount(uint8_t reg){return std::count_if(packets.begin(),packets.end(),[reg](const auto& p){return p.command==2&&p.address==(uint64_t(reg)<<8);});}
unsigned pixelCount(){return std::count_if(packets.begin(),packets.end(),[](const auto& p){return p.command==0x32;});}
void clear(){
 assert(!state.owned&&!bus&&!device&&!acquired&&!flight&&!allocation);
 calls={};failAt={};endError=ESP_ERR_TIMEOUT;dmaFailure=partialAdd=false;
 levels={};levels[12]=1;packets.clear();resets.clear();delays.clear();clockUs=clockReads=0;
 RiscPerf::configure(now,owner,true);
}
}
BaseType_t xPortGetCoreID(){return model::core;}
TaskHandle_t xTaskGetCurrentTaskHandle(){return model::task;}
void vTaskDelay(TickType_t ticks){model::correctOwner();model::delays.push_back(ticks);model::clockUs+=ticks*1000;}
esp_err_t spi_bus_initialize(spi_host_device_t host,const spi_bus_config_t* b,spi_dma_chan_t dma){
 using namespace model;correctOwner();assert(!bus&&host==SPI2_HOST&&dma==SPI_DMA_CH_AUTO);
 assert(b->sclk_io_num==11&&b->mosi_io_num==4&&b->miso_io_num==5&&b->quadwp_io_num==6&&b->quadhd_io_num==7);
 assert(b->data4_io_num==-1&&b->data5_io_num==-1&&b->data6_io_num==-1&&b->data7_io_num==-1);
 assert(b->max_transfer_sz==1640&&(b->flags&SPICOMMON_BUSFLAG_QUAD)==SPICOMMON_BUSFLAG_QUAD);
 assert(b->isr_cpu_id==ESP_INTR_CPU_AFFINITY_AUTO);
 if(failed(Init))return ESP_ERR_INVALID_STATE;bus=true;return ESP_OK;
}
esp_err_t spi_bus_add_device(spi_host_device_t host,const spi_device_interface_config_t* d,spi_device_handle_t* out){
 using namespace model;correctOwner();assert(bus&&!device&&host==SPI2_HOST);
 assert(d->command_bits==8&&d->address_bits==24&&!d->dummy_bits&&!d->mode&&d->clock_speed_hz==40000000);
 assert(d->clock_source==SPI_CLK_SRC_DEFAULT&&d->spics_io_num==-1&&d->flags==SPI_DEVICE_HALFDUPLEX&&d->queue_size==1);
 const bool bad=failed(Add);if(bad&&!partialAdd)return ESP_ERR_NO_MEM;
 device=true;*out=&handle;return bad?ESP_ERR_NO_MEM:ESP_OK;
}
esp_err_t spi_device_acquire_bus(spi_device_handle_t d,uint32_t wait){
 using namespace model;correctOwner();assert(device&&d==&handle&&!acquired&&wait==portMAX_DELAY);
 if(failed(Acquire))return ESP_FAIL;acquired=true;return ESP_OK;
}
esp_err_t spi_device_polling_start(spi_device_handle_t d,spi_transaction_t* t,uint32_t wait){
 using namespace model;correctOwner();assert(bus&&device&&acquired&&!flight&&d==&handle&&wait==portMAX_DELAY&&levels[12]==0);
 if(failed(Start))return ESP_ERR_NO_MEM;
 assert(!t->rxlength&&!t->rx_buffer&&t->length%8==0);
 if(t->cmd==2)assert((t->flags&(SPI_TRANS_MULTILINE_CMD|SPI_TRANS_MULTILINE_ADDR))==(SPI_TRANS_MULTILINE_CMD|SPI_TRANS_MULTILINE_ADDR)&&!(t->flags&SPI_TRANS_MODE_QIO));
 else assert(t->cmd==0x32&&t->addr==0x003c00&&t->flags==SPI_TRANS_MODE_QIO&&t->length==1640*8&&t->tx_buffer==allocation);
 Packet p{t->cmd,t->addr,t->flags,{}};
 const auto* bytes=static_cast<const uint8_t*>((t->flags&SPI_TRANS_USE_TXDATA)?static_cast<void*>(t->tx_data):t->tx_buffer);
 if(t->length)p.bytes.assign(bytes,bytes+t->length/8);
 packets.push_back(std::move(p));descriptor=t;flight=true;clockUs+=3;return ESP_OK;
}
esp_err_t spi_device_polling_end(spi_device_handle_t d,uint32_t wait){
 using namespace model;correctOwner();assert(flight&&device&&acquired&&d==&handle&&wait<=21);
 assert(descriptor==&state.transaction&&levels[12]==0);
 const auto& p=packets.back();assert(p.command==descriptor->cmd&&p.address==descriptor->addr&&p.bytes.size()==descriptor->length/8);
 const void* bytes=(descriptor->flags&SPI_TRANS_USE_TXDATA)?static_cast<void*>(descriptor->tx_data):descriptor->tx_buffer;
 if(!p.bytes.empty())assert(std::memcmp(p.bytes.data(),bytes,p.bytes.size())==0);
 if(failed(End)){
  if(dmaFailure){descriptor->flags|=SPI_TRANS_DMA_TX_FAIL;flight=false;packets.back().complete=true;return ESP_ERR_INVALID_STATE;}
  return endError;
 }
 flight=false;packets.back().complete=true;clockUs+=7;return ESP_OK;
}
void spi_device_release_bus(spi_device_handle_t d){using namespace model;correctOwner();assert(device&&acquired&&!flight&&d==&handle);acquired=false;}
esp_err_t spi_bus_remove_device(spi_device_handle_t d){using namespace model;correctOwner();assert(device&&!acquired&&!flight&&d==&handle);if(failed(Remove))return ESP_FAIL;device=false;return ESP_OK;}
esp_err_t spi_bus_free(spi_host_device_t h){using namespace model;correctOwner();assert(bus&&!device&&!flight&&h==SPI2_HOST);if(failed(Free))return ESP_FAIL;bus=false;return ESP_OK;}
esp_err_t gpio_set_level(gpio_num_t pin,uint32_t value){
 using namespace model;correctOwner();assert((pin==12||pin==8)&&value<=1);
 if(pin==12&&value)assert(!flight);
 if(failed(Level))return ESP_FAIL;levels[pin]=value;return ESP_OK;
}
esp_err_t gpio_config(const gpio_config_t* c){
 using namespace model;correctOwner();assert(c->mode==GPIO_MODE_OUTPUT&&!c->pull_up_en&&!c->pull_down_en&&c->intr_type==GPIO_INTR_DISABLE);
 assert(c->pin_bit_mask==(UINT64_C(1)<<12)||c->pin_bit_mask==(UINT64_C(1)<<8));
 return failed(Configure)?ESP_FAIL:ESP_OK;
}
esp_err_t gpio_reset_pin(gpio_num_t pin){using namespace model;correctOwner();assert(!bus&&!device&&!flight);resets.push_back(pin);return failed(Reset)?ESP_FAIL:ESP_OK;}
esp_err_t gpio_dump_io_configuration(FILE*,uint64_t){return ESP_OK;}
void* heap_caps_aligned_alloc(size_t alignment,size_t bytes,uint32_t caps){
 using namespace model;correctOwner();assert(!allocation&&alignment==16&&bytes==1640&&caps==(MALLOC_CAP_INTERNAL|MALLOC_CAP_DMA|MALLOC_CAP_8BIT));
 if(failed(Allocate))return nullptr;return posix_memalign(&allocation,alignment,bytes)?nullptr:allocation;
}
void heap_caps_free(void* p){using namespace model;correctOwner();assert(p==allocation&&!flight&&!bus&&!device);std::free(p);allocation=nullptr;}
static risc_hw_spi_display_v2 config(){
 risc_hw_spi_display_v2 c{};auto& b=c.base;b.struct_size=sizeof(c);b.width=410;b.height=502;b.offset_x=22;
 b.reset=8;b.cs=12;b.dc=b.backlight=b.busy=-1;b.bus.sclk=11;b.bus.mosi=4;b.bus.miso=5;b.bus.frequency_hz=40000000;
 c.data2=6;c.data3=7;return c;
}
static risc_hardware_device_v1 hardware(const risc_hw_spi_display_v2& c){
 risc_hardware_device_v1 h{};h.api_version=1;h.struct_size=sizeof(h);h.compatible="chipone,co5300";
 h.config_type="display.spi";h.config_version=2;h.config_size=sizeof(c);h.config=&c;return h;
}
static auto* api=RiscCpu::selectedDisplayBackend();
static void open(){const auto c=config();const auto h=hardware(c);assert(api->accepts(h,2)&&api->open(h,2));}
static void closed(){assert(api->close());assert(api->close());assert(!state.owned&&!model::allocation&&!model::bus&&!model::device&&!model::flight);}
static void checkPixels(size_t firstPacket,bool zero){
 using namespace model;unsigned expectedY=0;
 for(size_t i=firstPacket;i<packets.size();++i){const auto& p=packets[i];if(p.command!=0x32)continue;
  assert(i>=3&&p.complete&&p.bytes.size()==1640);
  const auto& x=packets[i-3];const auto& y=packets[i-2];const auto& ram=packets[i-1];
  assert(x.address==0x2a00&&x.bytes==std::vector<uint8_t>({0,22,1,175}));
  assert(y.address==0x2b00&&y.bytes==std::vector<uint8_t>({uint8_t(expectedY>>8),uint8_t(expectedY),uint8_t((expectedY+1)>>8),uint8_t(expectedY+1)}));
  assert(ram.address==0x2c00&&ram.bytes.empty());
  for(unsigned k=0;k<820;++k){const uint16_t value=zero?0:uint16_t(expectedY*410+k);assert(p.bytes[2*k]==value>>8&&p.bytes[2*k+1]==(value&255));}
  expectedY+=2;
 }
 assert(expectedY==502);
}
static void frame(unsigned end=502){
 uint16_t line[410];for(unsigned y=0;y<end;++y){for(unsigned x=0;x<410;++x)line[x]=uint16_t(y*410+x);assert(api->row(y,line,410));std::fill(std::begin(line),std::end(line),0xffff);}
}
#ifdef RISC_VENDOR_DISPLAY_PROBE
static void checkProbe(){
 using namespace model;
 assert(lit()==1&&registerCount(0x23)==1&&registerCount(0x13)==1&&pixelCount()==251*5);
 const uint16_t colors[]={0,0xf800,0x07e0,0x001f,0};unsigned pixels=0;
 for(const auto& p:packets){
  if(p.command==2&&p.address==0x5100&&!p.bytes.empty()&&p.bytes[0])assert(pixels==251&&p.bytes[0]==80);
  if(p.command!=0x32)continue;
  assert(p.complete&&p.bytes.size()==1640);const auto color=colors[pixels/251];
  for(unsigned k=0;k<820;++k)assert(p.bytes[2*k]==color>>8&&p.bytes[2*k+1]==(color&255));
  ++pixels;
 }
 assert(packets.back().command==0x32&&state.requestedBrightness==0&&!state.frameComplete);
 assert(delays==std::vector<TickType_t>({11,201,201,121,11,801,1201,1201,1201}));
}
#endif
int main(int argc,char** argv){
 using namespace model;
#ifdef RISC_VENDOR_DISPLAY_PROBE
 if(argc==2){
  clear();fault(End,std::strtoul(argv[1],nullptr,10));const auto c=config();
  assert(!api->open(hardware(c),2)&&flight&&!state.frameComplete);auto* retained=allocation;
  fault(End);assert(!api->close()&&flight&&allocation==retained&&resets.empty());closed();
  // A failed explicit probe is retried after cleanup, not marked completed.
  clear();open();checkProbe();closed();
  std::puts("Explicit diagnostic timeout retains DMA custody and retries full probe: PASS");return 0;
 }
#endif
 assert(argc==1);(void)argv;
 clear();const auto valid=config();auto h=hardware(valid);uint16_t line[410]{};
 assert(!api->row(0,line,410)&&!api->brightness(80));
 assert(!api->accepts(h,3));h.config=nullptr;assert(!api->accepts(h,2));h=hardware(valid);h.compatible=nullptr;assert(!api->accepts(h,2));
 for(unsigned which=0;which<9;++which){auto c=config();
  switch(which){case 0:c.base.width=412;break;case 1:c.base.height=500;break;case 2:c.base.offset_x=0;break;case 3:c.base.rotation=1;break;case 4:c.base.bus.frequency_hz=80000000;break;case 5:c.base.bus.mode=1;break;case 6:c.data3=c.data2;break;case 7:c.base.cs=-1;break;case 8:c.base.reset_active_high=true;break;}
  auto bad=hardware(c);assert(!api->accepts(bad,2)&&!api->open(bad,2));
 }
 assert(std::all_of(calls.begin(),calls.end(),[](unsigned n){return n==0;}));
 open();
 // Both branches first program brightness zero before DISPON; the explicit
 // probe's later nonzero command is separately checked below.
 assert(packets[6].address==0x5100&&packets[6].bytes==std::vector<uint8_t>({0}));
 assert(packets[7].address==0x2900&&packets[7].bytes.empty());
 assert(packets[8].address==0x5100&&packets[8].bytes==std::vector<uint8_t>({0}));
#ifdef RISC_VENDOR_DISPLAY_PROBE
 checkProbe();
#else
 assert(lit()==0&&pixelCount()==251);checkPixels(0,true);
 assert(registerCount(0x23)==0&&registerCount(0x13)==0);
 assert(delays==std::vector<TickType_t>({11,201,201,121,11}));
#endif
 // A brightness request cannot illuminate boot clearing or an incomplete frame.
 const auto before=packets.size();const auto beforeLit=lit();assert(api->brightness(80)&&packets.size()==before);
 assert(!api->row(1,line,410)&&!api->row(0,line,409)&&!api->row(502,line,410));
 frame(500);assert(lit()==beforeLit&&!state.frameComplete);
 for(unsigned x=0;x<410;++x)line[x]=uint16_t(500*410+x);assert(api->row(500,line,410));
 std::fill(std::begin(line),std::end(line),0xffff);
 assert(!api->row(498,line,410)&&lit()==beforeLit);
 for(unsigned x=0;x<410;++x)line[x]=uint16_t(501*410+x);assert(api->row(501,line,410));
 assert(lit()==beforeLit+1&&state.frameComplete);checkPixels(before,false);
 assert(packets.back().address==0x5100&&packets.back().bytes[0]==80&&packets[packets.size()-2].complete);
#if RISC_PERFORMANCE_TRACE
 assert(clockReads==503&&RiscPerf::data.counts[34]==1&&RiscPerf::data.values[34]==502&&RiscPerf::data.values[35]==251);
 assert(RiscPerf::data.durations_us[34]==RiscPerf::data.durations_us[35]+RiscPerf::data.durations_us[36]);
#else
 assert(clockReads==0);
#endif
 auto callsBefore=calls;core=1;assert(!api->brightness(0)&&!api->row(0,line,410)&&!api->close()&&calls==callsBefore);core=0;
 task=reinterpret_cast<TaskHandle_t>(2);assert(!api->close()&&calls==callsBefore);task=reinterpret_cast<TaskHandle_t>(1);
 assert(api->brightness(0)&&packets.back().bytes[0]==0);closed();
 assert(registerCount(0x28)==1&&registerCount(0x10)==1&&resets.size()==7);
 // No full-frame gate from an out-of-order set of pairs.
 clear();open();assert(api->brightness(90));assert(api->row(2,line,410)&&api->row(3,line,410));
 for(unsigned y=4;y<502;++y)assert(api->row(y,line,410));assert(!state.frameComplete&&lit()==0);closed();
 // Every setup boundary can fail without losing exact cleanup custody.
 for(auto op:{Init,Add,Acquire,Allocate,Configure,Level}){
  clear();fault(op);const auto c=config();const auto hw=hardware(c);assert(!api->open(hw,2)&&state.owned);closed();
  if(op==Init)assert(calls[Free]==0&&resets==std::vector<int>({12}));
 }
 clear();partialAdd=true;fault(Add);{const auto c=config();assert(!api->open(hardware(c),2)&&device);closed();}
 // Register, reset and early/late boot clearing failures stay dark.
 for(unsigned n:{2u,3u,4u}){clear();fault(Level,n);const auto c=config();assert(!api->open(hardware(c),2));closed();}
 for(unsigned n:{1u,7u,12u,13u,16u,1016u}){
  clear();fault(Start,n);const auto c=config();assert(!api->open(hardware(c),2)&&lit()==0);closed();
 }
 for(unsigned n:{1u,7u,16u,1016u}){
  clear();fault(End,n);const auto c=config();assert(!api->open(hardware(c),2)&&flight&&lit()==0);
  auto* kept=allocation;const auto descriptorCopy=state.transaction;fault(End);assert(!api->close()&&flight&&allocation==kept&&resets.empty());
  assert(std::memcmp(&descriptorCopy,&state.transaction,sizeof(descriptorCopy))==0);closed();
 }
 // A timed-out final pair never opens the visibility gate, even after close
 // later proves that transfer completed. Caller pixels and descriptor stay held.
 clear();open();assert(api->brightness(80));frame(501);fault(End,4);assert(!api->row(501,line,410)&&flight&&!state.frameComplete&&lit()==0);
 assert(!api->brightness(255)&&!api->row(501,line,410));closed();assert(lit()==0);
 // IDF6's completed-DMA-error status is distinct from still-in-flight timeout.
 clear();open();assert(api->row(0,line,410));dmaFailure=true;fault(End,4);assert(!api->row(1,line,410)&&!flight&&state.failed);closed();
 // CS deassertion failure retains the completed transaction until safely high.
 clear();open();fault(Level,2);assert(!api->brightness(0)&&!flight&&state.selected);closed();
 // Sleep command stages resume after completion without duplicate commands.
 for(unsigned n:{1u,2u}){clear();open();fault(End,n);assert(!api->close()&&flight&&device&&bus&&allocation);closed();assert(registerCount(0x28)==1&&registerCount(0x10)==1);}
 for(auto op:{Remove,Free}){clear();open();fault(op);assert(!api->close()&&state.owned&&allocation&&resets.empty());closed();assert(registerCount(0x28)==1&&registerCount(0x10)==1);}
 for(unsigned n=1;n<=7;++n){clear();open();fault(Reset,n);assert(!api->close()&&allocation&&!bus&&!device&&resets.size()==n);const auto held=resets.back();closed();assert(resets[n]==held&&resets.size()==8);}
 // Partial frames produce exactly one abort across failed cleanup retries.
 clear();open();assert(api->row(0,line,410));fault(Remove);assert(!api->close());
#if RISC_PERFORMANCE_TRACE
 assert(RiscPerf::data.counts[39]==1&&RiscPerf::data.values[39]==1);
#endif
 closed();
#if RISC_PERFORMANCE_TRACE
 assert(RiscPerf::data.counts[39]==1);
#endif
 // An unclassified poll error is irreversible uncertainty: no re-poll, pad
 // reset, resource release or new open. The following reset is test-process only.
 clear();open();assert(api->row(0,line,410));endError=ESP_FAIL;fault(End);assert(!api->row(1,line,410)&&state.uncertain);
 callsBefore=calls;assert(!api->close()&&!api->close()&&calls==callsBefore&&resets.empty());
 {const auto c=config();assert(!api->open(hardware(c),2));}
 std::free(allocation);allocation=nullptr;state=PanelState{};bus=device=acquired=flight=false;
 std::printf("Native IDF6 CO5300: real SDK/ABI, 40MHz framing, 251 paired windows, dark frame gate, setup/transfer/cleanup faults, retained custody and trace=%d PASS\n",RISC_PERFORMANCE_TRACE);
}
