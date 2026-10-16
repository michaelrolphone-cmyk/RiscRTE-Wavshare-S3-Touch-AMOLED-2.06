#!/usr/bin/env python3
"""Join actual Wave SD/FatFs and Reader MSC/TinyUSB with modeled peripherals."""
import argparse,os,subprocess,tempfile
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
for name in ('sdk','support-include','reader','tinyusb'):p.add_argument('--'+name,type=Path,required=True)
p.add_argument('--sanitize',action='store_true');a=p.parse_args();r=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory() as td:
 b=Path(td);stack=b/'stack';reader=a.reader.resolve()
 subprocess.run(['python3',str(reader/'scripts/prepare_usb_device_stack.py'),'--source',str(a.tinyusb.resolve()),'--output',str(stack)],check=True)
 flags=['-fsanitize=address,undefined','-fno-sanitize-recover=all','-fno-omit-frame-pointer','-fno-pie','-no-pie'] if a.sanitize else []
 inc=[a.sdk.resolve(),a.support_include.resolve(),r/'include',reader/'sdk/driver',reader/'test/usb_device_msc',reader/'Drivers/usb_device_msc_esp32s3',stack]
 sources=[r/'tests/test_usb_storage.c',r/'tests/usb_storage_bridge.c',*[r/'lib/storage_fatfs/fatfs'/x for x in ('ff.c','ffunicode.c')],*[reader/'Drivers/usb_device_msc_esp32s3'/x for x in ('driver.c','StackDefaults.c')],*[stack/x for x in ('tusb.c','common/tusb_fifo.c','device/usbd.c','device/usbd_control.c','class/msc/msc_device.c')]]
 subprocess.run([os.environ.get('CC','cc'),'-std=c11','-O1','-g','-Wall','-Wextra','-Werror','-Wno-unused-function','-Wno-unused-parameter','-Wno-misleading-indentation','-Wno-overflow',*flags,*['-I'+str(q) for q in inc],*map(str,sources),'-o',str(b/'test')],check=True)
 for case in ('eject','disconnect'):subprocess.run([str(b/'test'),case],check=True,timeout=30,env=dict(os.environ,ASAN_OPTIONS='detect_leaks=0',UBSAN_OPTIONS='halt_on_error=1'))
