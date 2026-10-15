#!/usr/bin/env python3
"""Prove the selected product anchor pulls an otherwise optional archive member.

Uses the production hook/anchor declarations with a minimal inert backend on the
host linker. Physical bridge behavior is covered by test_vendor_idf6.py; the
fresh native candidate must still prove its exact strong hook and timing marker.
"""
from pathlib import Path
import re
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
source = (ROOT / 'native/VendorDisplayIdf6.inc').read_text()
hook = 'namespace RiscCpu {const DisplayBackend* selectedDisplayBackend(){return &backend;}}'
anchor = 'extern "C" const uint32_t risc_waveshare_native_display_anchor=1;'
assert source.count(hook) == source.count(anchor) == 1
assert '"-Wl,-u,risc_waveshare_native_display_anchor"' in (ROOT / 'profiles/native-idf61.cmake').read_text()
with tempfile.TemporaryDirectory(prefix='wave-display-archive-') as temporary:
    root = Path(temporary)
    shared = '#include <cstdint>\nnamespace RiscCpu {struct DisplayBackend {uint32_t identity;};}\n'
    (root / 'display.cpp').write_text(shared + 'namespace {const RiscCpu::DisplayBackend backend{0x5300};}\n' + hook + '\n' + anchor + '\n')
    (root / 'main.cpp').write_text(shared + 'namespace RiscCpu {const DisplayBackend* selectedDisplayBackend() __attribute__((weak));}\nint main(){if(!RiscCpu::selectedDisplayBackend)return 2;return RiscCpu::selectedDisplayBackend()->identity==0x5300?0:3;}\n')
    for name in ('display', 'main'):
        subprocess.run(['c++', '-std=c++17', '-ffunction-sections', '-fdata-sections', '-c', str(root / (name + '.cpp')), '-o', str(root / (name + '.o'))], check=True)
    subprocess.run(['ar', 'rcs', str(root / 'display.a'), str(root / 'display.o')], check=True)
    for retained, expected in ((False, 2), (True, 0)):
        output = root / ('retained' if retained else 'unselected')
        command = ['c++', '-Wl,--gc-sections', str(root / 'main.o'), str(root / 'display.a'), '-o', str(output)]
        if retained: command += ['-Wl,-u,risc_waveshare_native_display_anchor']
        subprocess.run(command, check=True)
        assert subprocess.run([str(output)]).returncode == expected
        labels = subprocess.check_output(['nm', str(output)], text=True)
        assert bool(re.search(r'\bR risc_waveshare_native_display_anchor$', labels, re.M)) == retained
        assert bool(re.search(r'\bT _ZN7RiscCpu22selectedDisplayBackendEv$', labels, re.M)) == retained
print('Product-owned anchor extracts the strong display backend; absent-anchor negative PASS')
