from pathlib import Path
import subprocess,tempfile,os,argparse
p=argparse.ArgumentParser();p.add_argument("--sanitize",action="store_true");a=p.parse_args()
src=(Path(__file__).resolve().parents[1]/'native/VendorDisplay.cpp').read_text();close=src[src.index('bool closePanel('):src.index('\nbool openPanel(')];row=src[src.index('bool row('):src.index('\nbool brightness(')]
pre=r'''
#include <cstdint>
#include <cstddef>
#include <cstring>
#include <cassert>
#include <vector>
#include <cstdio>
using gpio_num_t=int;constexpr int ESP_OK=0;int failPin=-1;std::vector<int> resets;int gpio_reset_pin(int p){resets.push_back(p);return p==failPin?-1:0;}
struct Bus{bool clean=true;unsigned calls=0;bool riscClose(){++calls;return clean;}}*bus=nullptr;int16_t cs=-1,reset=-1;
struct Packet{unsigned y,w,h;std::vector<uint16_t> pixels;};
bool panelReady=true,panelOff=false;unsigned offCalls=0;
struct Panel{void displayOff(){++offCalls;assert(bus&&bus->calls==0);}std::vector<Packet> packets;void startWrite(){}void endWrite(){}void writeAddrWindow(int x,unsigned y,unsigned w,unsigned h){assert(x==0);packets.push_back({y,w,h,{}});}void writePixels(uint16_t* p,unsigned n){packets.back().pixels.assign(p,p+n);}} storage,*panel=&storage;
struct Log{template<class... A>void printf(const char*,A...){}} Serial;
void pads(const char*){}
uint16_t width=410,height=502,paired[820];uint32_t pendingRow=UINT32_MAX;
'''
post=r'''
int main(){uint16_t line[410]={};assert(!row(1,line,410));assert(!row(0,line,409));assert(!row(502,line,410));
for(unsigned y=0;y<502;y++){for(unsigned x=0;x<410;x++)line[x]=(y*410+x)%65536;auto before=storage.packets.size();assert(row(y,line,410));assert(storage.packets.size()==before+(y%2));}
assert(storage.packets.size()==251&&pendingRow==UINT32_MAX);
for(auto& p:storage.packets){assert(p.y%2==0&&p.w==410&&p.h==2&&p.pixels.size()==820);for(unsigned i=0;i<820;i++)assert(p.pixels[i]==(p.y*410+i)%65536);}
assert(row(0,line,410));assert(!row(2,line,410));assert(row(1,line,410));
// Failed bus cleanup must not release either pad. Failed CS/reset retains
// objects and the unclean pin identity; a retry completes only remaining work.
panel=new Panel;bus=new Bus;bus->clean=false;cs=12;reset=8;pendingRow=4;
assert(!closePanel()&&offCalls==1&&resets.empty()&&panel&&bus&&pendingRow==4);
bus->clean=true;failPin=12;assert(!closePanel()&&cs==12&&reset==8&&panel&&bus);
failPin=8;assert(!closePanel()&&cs==-1&&reset==8&&panel&&bus);
auto n=resets.size();failPin=-1;assert(closePanel());assert(resets.size()==n+1&&resets.back()==8);
assert(offCalls==1&&!panelReady&&!panelOff);
assert(!panel&&!bus&&cs==-1&&reset==-1&&!width&&!height&&pendingRow==UINT32_MAX);
assert(closePanel()&&resets.size()==n+1);
puts("Native display: 251 aligned windows, 205820 pixels ordered, invalid rows rejected; bus/CS/reset cleanup retry and retained state PASS");}
'''
with tempfile.TemporaryDirectory() as tmp:
 source=Path(tmp)/'native.cpp';binary=Path(tmp)/'native';source.write_text(pre+row+close+post)
 flags=['-fsanitize=address,undefined','-fno-sanitize-recover=all','-fno-omit-frame-pointer'] if a.sanitize else []
 subprocess.run([os.environ.get('CXX','c++'),'-std=c++17','-Wall','-Wextra','-Werror',*flags,str(source),'-o',str(binary)],check=True)
 subprocess.run([str(binary)],check=True)
