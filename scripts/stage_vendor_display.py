#!/usr/bin/env python3
"""Stage pinned vendor source plus cleanup lifecycle extension and checked SPI return codes."""
from pathlib import Path
import argparse,shutil,json,hashlib,subprocess
p=argparse.ArgumentParser();p.add_argument('--vendor',type=Path,required=True);p.add_argument('--runtime',type=Path,required=True);a=p.parse_args()
root=Path(__file__).resolve().parents[1]
assert subprocess.check_output(['git','-C',str(a.vendor),'rev-parse','HEAD'],text=True).strip()=='b099739ad0e33b34e5fbaae77f02bd84805d79a3'
src=a.vendor/'examples/arduino/libraries/Arduino_GFX';dst=a.runtime/'lib/WaveshareVendorGfx'
shutil.copytree(src,dst,dirs_exist_ok=True)
selected=['Arduino_G.cpp','Arduino_DataBus.cpp','Arduino_GFX.cpp','Arduino_TFT.cpp','Arduino_OLED.cpp','databus/Arduino_ESP32QSPI.cpp','display/Arduino_CO5300.cpp']
proof={x:hashlib.sha256((src/'src'/x).read_bytes()).hexdigest() for x in selected}
(dst/'library.json').write_text(json.dumps({'name':'WavesharePinnedVendorGfx','version':'1.6.0','build':{'srcFilter':['-<*>']+['+<'+x+'>' for x in selected]}}))
h=dst/'src/databus/Arduino_ESP32QSPI.h';s=h.read_text();s=s.replace('  void beginWrite() override;','  bool riscClose(); // Cleanup extension; SPI return codes are checked.\n  void beginWrite() override;').replace('  spi_device_handle_t _handle;','  spi_device_handle_t _handle=nullptr;\n  bool _riscBusInitialized=false, _riscBusAcquired=false;').replace('uint8_t* _buffer;','uint8_t* _buffer=nullptr;').replace('uint8_t *_2nd_buffer;','uint8_t *_2nd_buffer=nullptr;');h.write_text(s)
c=dst/'src/databus/Arduino_ESP32QSPI.cpp';s=c.read_text();s=s.replace('  spi_device_interface_config_t devcfg = {','  _riscBusInitialized=true;\n  spi_device_interface_config_t devcfg = {',1).replace('    spi_device_acquire_bus(_handle, portMAX_DELAY);','    spi_device_acquire_bus(_handle, portMAX_DELAY);\n    _riscBusAcquired=true;',1)
# Preserve transaction fields and wire traffic; fail loudly on SDK errors.
for call in ('spi_device_acquire_bus(_handle, portMAX_DELAY)', 'spi_device_polling_start(_handle, _spi_tran, portMAX_DELAY)', 'spi_device_polling_end(_handle, portMAX_DELAY)'):
 assert call+';' in s
 s=s.replace(call+';', 'ESP_ERROR_CHECK('+call+');')
cleanup="""
bool Arduino_ESP32QSPI::riscClose() {
  if(_handle){
    if(_riscBusAcquired){spi_device_release_bus(_handle);_riscBusAcquired=false;}
    if(spi_bus_remove_device(_handle)!=ESP_OK)return false;
    _handle=nullptr;
  }
  if(_riscBusInitialized){if(spi_bus_free(ESP32QSPI_SPI_HOST)!=ESP_OK)return false;_riscBusInitialized=false;}
  if(_buffer){heap_caps_free(_buffer);_buffer=nullptr;}
  if(_2nd_buffer){heap_caps_free(_2nd_buffer);_2nd_buffer=nullptr;}
  return true;
}
"""
s=s.replace('#endif // #if defined(ESP32)',cleanup+'\n#endif // #if defined(ESP32)');c.write_text(s)
shutil.copy2(root/'native/VendorDisplay.cpp',a.runtime/'src/VendorDisplay.cpp')
(root/'vendor-source-hashes.json').write_text(json.dumps(proof,indent=2)+'\n')
print('Pinned vendor source staged; command/reset/transaction fields preserved; SPI results checked.')
