"""Run the production openPanel body with observable vendor API boundaries."""
from pathlib import Path
import subprocess,tempfile,os
root=Path(__file__).resolve().parents[1]
s=(root/'native/VendorDisplay.cpp').read_text();body=s[s.index('bool openPanel('):s.index('\nbool row(')]
pre=r'''
#include <cassert>
#include <cstdint>
#include <cstddef>
#include <new>
#include <vector>
struct Base {int width=410,height=502,reset=8,cs=12,rotation=0,offset_x=22,offset_y=0;struct {int sclk=1,mosi=2,miso=3,frequency_hz=40000000;} bus;};
struct risc_hw_spi_display_v2 {Base base;int data2=4,data3=5;};
struct risc_hardware_device_v1 {const void*config;};
bool accepts(const risc_hardware_device_v1&,uint8_t){return true;}
unsigned delays=0,commands=0;std::vector<int> lights,fills;
void delay(unsigned n){delays+=n;}void pads(const char*){}
struct Log {void println(const char*){}} Serial;
struct Arduino_ESP32QSPI {template<class...T>Arduino_ESP32QSPI(T...){}void sendCommand(int){commands++;}}*bus=nullptr;
struct Arduino_CO5300 {template<class...T>Arduino_CO5300(T...){}bool begin(int){return true;}void setBrightness(int n){lights.push_back(n);}void fillScreen(int n){fills.push_back(n);}void startWrite(){}void endWrite(){}void writeAddrWindow(int,int,int,int){}void writePixels(uint16_t*,unsigned){}}*panel=nullptr;
uint16_t width=0,height=0,paired[820];int16_t reset=-1,cs=-1;bool panelReady=false,panelOff=false;uint32_t pendingRow=UINT32_MAX;
#ifdef RISC_VENDOR_DISPLAY_PROBE
bool probed=false;
#endif
'''
post=r'''
int main(){risc_hw_spi_display_v2 c;risc_hardware_device_v1 hw{&c};assert(openPanel(hw,2));
assert(panelReady&&!panelOff&&width==410&&height==502&&lights.front()==0&&lights.back()==0&&fills.back()==0);
#ifdef RISC_VENDOR_DISPLAY_PROBE
assert(delays==4400&&commands==2&&probed&&fills.front()==0xf800);
#else
assert(!delays&&!commands&&fills.size()==1);for(auto n:lights)assert(n==0);
#endif
delete panel;delete bus;
}
'''
with tempfile.TemporaryDirectory() as d:
 p=Path(d)/'boot.cpp';p.write_text(pre+body+post)
 for diagnostic in (False,True):
  out=Path(d)/str(diagnostic)
  subprocess.run([os.environ.get('CXX','c++'),'-std=c++17','-Wall','-Wextra','-Werror',*(['-DRISC_VENDOR_DISPLAY_PROBE'] if diagnostic else []),str(p),'-o',str(out)],check=True)
  subprocess.run([str(out)],check=True)
print('Production boot: black-only, no diagnostic commands or delays; explicit probe build preserved PASS')
