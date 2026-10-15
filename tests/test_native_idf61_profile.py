#!/usr/bin/env python3
"""Keep the native profile's capabilities/settings equal to the shipped base."""
import argparse
import re
import subprocess
from pathlib import Path
BASE='4107eaeedd8c801eeaf7deb1c7bc4a943cd27342'
ROOT=Path(__file__).resolve().parents[1]
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--runtime',type=Path,required=True);a=p.parse_args()
    def base(name):return subprocess.check_output(['git','-C',str(a.runtime),'show',BASE+':'+name])
    old=base('expanded-candidate.ini').decode()
    expected=set(re.findall(r'-D(RISC_[A-Z0-9_]+=\d+)',old))
    expected|={'RISC_PERFORMANCE_TRACE=1','RISC_PERFORMANCE_TRACE_CAPACITY=64'}
    profile=(ROOT/'profiles/native-idf61.cmake').read_text()
    selected=set(re.findall(r'\b(RISC_[A-Z0-9_]+=\d+)\b',profile))
    assert selected==expected,{'missing':sorted(expected-selected),'extra':sorted(selected-expected)}
    assert (ROOT/'profiles/native-idf61-settings.h').read_bytes()==base('waveshare-settings-profile.h')
    assert (a.runtime/'partitions-paired-appdata-expanded.csv').read_bytes()==base('partitions-paired-appdata-expanded.csv')
    assert 'RISC_NATIVE_APPDATA ON' in profile and 'RISC_NATIVE_IQ ON' in profile
    assert 'VendorDisplay.cpp' in profile and 'Arduino' not in profile
    assert 'RISC_NATIVE_TARGET "esp32s3-16mb-waveshare-expanded"' in profile
    for symbol in re.findall(r'-Wl,-u,([a-zA-Z0-9_]+)',old):
        assert '-Wl,-u,'+symbol in profile,symbol
    print('Native Waveshare profile preserves shipped capabilities, settings, layout and retained symbols PASS')
if __name__=='__main__':main()
