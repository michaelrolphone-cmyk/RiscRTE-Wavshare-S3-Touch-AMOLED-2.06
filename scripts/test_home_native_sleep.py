#!/usr/bin/env python3
"""Bridge real shared Home and Waveshare power to native CPU/serial sleep guards.

Expected baseline records the pre-fix -3 refusal; expected fixed requires actual
terminal Deep. The same fixed expectation must fail against the baseline.
SDK/peripheral entry, panel and alarm are host models. No card, namespace,
serial session, device access or complete firmware build is involved.
"""
import argparse
import os
import subprocess
import tempfile
from pathlib import Path

p = argparse.ArgumentParser(description=__doc__)
for name in ('runtime', 'watch', 'utilities', 'idf'):
    p.add_argument('--' + name, type=Path, required=True)
p.add_argument('--expect', choices=('baseline', 'fixed'), default='fixed')
p.add_argument('--sanitize', action='store_true')
p.add_argument('--case', type=int, choices=range(7))
a = p.parse_args()
root = Path(__file__).resolve().parents[1]
r = a.runtime.resolve()
flags = ['-Wall', '-Wextra', '-Werror', '-Wno-misleading-indentation', '-g']
if a.sanitize:
    flags += ['-fsanitize=address,undefined', '-fno-sanitize-recover=all',
              '-fno-omit-frame-pointer', '-fno-pie', '-no-pie']
c_includes = [a.utilities / 'lib/Alarm/include', root / 'include',
              a.watch / 'sdk/driver', a.watch / 'sdk/app', a.watch / 'include',
              a.watch / 'apps/clock', r / 'sdk/hardware']
cpp_includes = [r / 'test/native_diagnostic_workspace_shim',
                r / 'test/native_sleep_diagnostics_idf6_shim',
                r / 'test/native_platform_shim',
                a.idf / 'components/esp_common/include',
                a.idf / 'components/esp_driver_usb_serial_jtag/include',
                a.idf / 'components/soc/esp32s3/include',
                a.idf / 'components/soc/include',
                r / 'src', r / 'sdk/app', r / 'sdk/driver', r / 'sdk/hardware',
                r / 'lib/ArduinoJson/src', r / 'test/drivers/stubs']
def includes(paths):
    return ['-I' + str(x.resolve()) for x in paths]
sources = ['bootstrap/Json.cpp', 'bootstrap/Board.cpp', 'bootstrap/Runtime.cpp',
           'runtime/streams/AppStreamSessions.cpp', 'runtime/streams/ProviderQueueHost.cpp',
           'runtime/drivers/ProviderGraphV2.cpp', 'runtime/drivers/ProviderModuleV2.cpp',
           'ports/esp32s3/CpuPort.cpp', 'runtime/serial/Files.cpp',
           'ports/esp32s3/NativePlatform.cpp', 'ports/esp32s3/NativeSerialFiles.cpp',
           'ports/esp32s3/SleepDiagnostics.cpp']
with tempfile.TemporaryDirectory(prefix='home-native-sleep-') as tmp:
    obj, target = Path(tmp) / 'home.o', Path(tmp) / 'native'
    subprocess.run([os.environ.get('CC', 'cc'), '-std=c11', '-fexceptions', *flags,
                    *includes(c_includes), '-c', str(root / 'tests/home_native_sleep_bridge.c'),
                    '-o', str(obj)], check=True)
    subprocess.run([os.environ.get('CXX', 'c++'), '-std=c++17', *flags,
                    '-Wno-missing-field-initializers',
                    '-DRISC_NATIVE_ESP_IDF=1', '-DRISC_CONSOLE_USB_SERIAL_JTAG=1',
                    '-DRISC_NATIVE_SERIAL_FILES=1', '-DRISC_ENABLE_USB_PHY=1',
                    '-DRISC_STAGE_LOGS=1', '-DRISC_SLEEP_DIAGNOSTICS=1',
                    '-DCONFIG_SPIRAM_ALLOW_BSS_SEG_EXTERNAL_MEMORY=1',
                    '-DCONFIG_SPIRAM_BOOT_INIT=1', *includes(cpp_includes),
                    *[str(r / 'src' / x) for x in sources],
                    str(root / 'tests/home_native_sleep_bridge.cpp'), str(obj),
                    '-ldl', '-o', str(target)], check=True)
    for scenario in (range(7) if a.case is None else [a.case]):
        subprocess.run([str(target), str(scenario), a.expect], check=True)
print('Home + Waveshare power + native CPU/serial bridge PASS (' + a.expect + ')')
