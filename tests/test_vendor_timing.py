#!/usr/bin/env python3
"""Production native display telemetry: bounded aggregates, disabled no-op, custody."""
from pathlib import Path
import argparse, os, subprocess, tempfile

p = argparse.ArgumentParser()
p.add_argument('--sanitize', action='store_true')
a = p.parse_args()
src = (Path(__file__).resolve().parents[1] / 'native/VendorDisplay.cpp').read_text()
timing = src[src.index('#if RISC_PERFORMANCE_TRACE\n// Owner-task-only'):src.index('bool accepts(')]
row = src[src.index('bool row('):src.index('\nbool brightness(')]
close = src[src.index('bool closePanel('):src.index('\nbool openPanel(')]
pre = r'''
#include <cstdint>
#include <cstddef>
#include <cstring>
#include <cassert>
#include <cstdio>
#include <vector>
uint64_t clockUs=0;unsigned clockReads=0;bool traceEnabled=true;
struct Event{uint32_t phase,value;uint64_t duration;};std::vector<Event> events;
namespace RiscPerf{
bool allowed(){return traceEnabled;}
uint64_t now(){++clockReads;return clockUs;}
void aggregate(uint32_t phase,uint32_t value,uint64_t duration){events.push_back({phase,value,duration});}
}
using gpio_num_t=int;constexpr int ESP_OK=0;int gpio_reset_pin(int){return ESP_OK;}
struct Bus{bool clean=true;bool riscClose(){return clean;}}*bus=new Bus;
struct Panel{void displayOff(){}void startWrite(){}void endWrite(){}
 void writeAddrWindow(int,unsigned,unsigned,unsigned){clockUs+=21;}
 void writePixels(uint16_t*,unsigned n){assert(n==820);clockUs+=85;}
}*panel=new Panel;
bool panelReady=true,panelOff=false;int16_t cs=12,reset=8;
uint16_t width=410,height=502,paired[820];uint32_t pendingRow=UINT32_MAX;
'''
post = r'''
int main(){
 uint16_t pixels[410]{};
 assert(!row(1,pixels,410));assert(!row(0,pixels,409));assert(!row(502,pixels,410));
 assert(clockReads==0&&events.empty());
 for(unsigned y=0;y<502;++y){clockUs+=3;assert(row(y,pixels,410));}
#if RISC_PERFORMANCE_TRACE
 assert(clockReads==503&&events.size()==5);
 assert(events[0].phase==34&&events[0].value==502&&events[0].duration==28109);
 assert(events[1].phase==35&&events[1].value==251&&events[1].duration==26606);
 assert(events[2].phase==36&&events[2].value==251&&events[2].duration==1503);
 assert(events[3].phase==37&&events[3].duration==106);
 assert(events[4].phase==38&&events[4].duration==6);
 assert(events[0].duration==events[1].duration+events[2].duration);
#else
 assert(clockReads==0&&events.empty());
#endif
 const auto completeEvents=events.size();assert(closePanel());assert(events.size()==completeEvents);
 panel=new Panel;bus=new Bus;width=410;height=502;panelReady=true;panelOff=false;
 assert(row(0,pixels,410));assert(!row(2,pixels,410));clockUs+=123;
 bus->clean=false;assert(!closePanel()&&panel&&bus&&pendingRow==0);
#if RISC_PERFORMANCE_TRACE
 assert(events.size()==completeEvents+1&&events.back().phase==39&&events.back().value==1&&events.back().duration==123);
#else
 assert(clockReads==0&&events.empty());
#endif
 const auto failedEvents=events.size();bus->clean=true;assert(closePanel());assert(events.size()==failedEvents);
 panel=new Panel;bus=new Bus;width=410;height=502;panelReady=true;panelOff=false;
 traceEnabled=false;const auto reads=clockReads;const auto count=events.size();
 for(unsigned y=0;y<502;++y)assert(row(y,pixels,410));
 assert(clockReads==reads&&events.size()==count);assert(closePanel());
 printf("Native timing trace=%d: 502 rows, exact transfer+gap sum, one abort through failed-close retry, disabled clock/log no-op PASS\n",RISC_PERFORMANCE_TRACE);
}
'''
with tempfile.TemporaryDirectory() as tmp:
    source = Path(tmp) / 'timing.cpp'
    source.write_text(pre + timing + row + close + post)
    for enabled in (0, 1):
        binary = Path(tmp) / ('timing-' + str(enabled))
        flags = ['-fsanitize=address,undefined', '-fno-sanitize-recover=all', '-fno-omit-frame-pointer'] if a.sanitize else []
        subprocess.run([os.environ.get('CXX', 'c++'), '-std=c++17', '-O2', '-ffunction-sections', '-fdata-sections', '-Wl,--gc-sections', '-Wall', '-Wextra', '-Werror', '-Wno-misleading-indentation',
                        '-DRISC_PERFORMANCE_TRACE=' + str(enabled), *flags, str(source), '-o', str(binary)], check=True)
        assert (b'RISCRTE_VENDOR_DISPLAY_TIMING_V1' in binary.read_bytes()) == bool(enabled)
        subprocess.run([str(binary)], check=True)
