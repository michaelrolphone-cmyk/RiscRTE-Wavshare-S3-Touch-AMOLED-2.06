import argparse,json,os,subprocess
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--sanitize',default='none');a=p.parse_args();base=a.root.resolve();r=base/'runtime';w=base/'wave';sys=base/'system';o=base/('out-'+a.sanitize.replace(',','-'));o.mkdir(exist_ok=True)
def run(cmd,**kw):subprocess.run([str(x) for x in cmd],check=True,**kw)
run(['python3',w/'tests/t051/prepare.py',r,o])
flags=['-O0','-g','-Wall','-Wextra','-Werror','-Wno-unused-function','-Wno-unused-variable','-Wno-overflow','-Wno-misleading-indentation','-Wno-missing-field-initializers','-fno-omit-frame-pointer']
if a.sanitize!='none':flags+=['-fsanitize='+a.sanitize,'-fno-sanitize-recover=all']
inc=['-I'+str(x) for x in [base/'sd-sdk',base/'support',w/'include',o,r,r/'src',r/'test',r/'test/drivers/stubs']]+['-isystem',str(r/'lib/ArduinoJson/src')]
run(['cc','-std=c11',*flags,*inc,'-shared','-fPIC',w/'tests/t051/sd_fixture.c',w/'lib/storage_fatfs/fatfs/ff.c',w/'lib/storage_fatfs/fatfs/ffunicode.c','-o',o/'driver.elf'])
selected=['-DRISC_NATIVE_SETTINGS_PORT_SELECTED=1','-DRISC_NATIVE_SETTINGS_NAMESPACE_MASK=2','-DRISC_NATIVE_SETTINGS_LIFECYCLE=1','-DRISC_NATIVE_SETTINGS_WORKER=1','-DRISC_RUNTIME_ATOMIC_KEY_VALUE=1','-DRISC_NATIVE_STORAGE_CUSTODY=1']
run(['c++','-std=c++17',*flags,*inc,*selected,'-DESP_PLATFORM','-I'+str(r/'test/native_nvs_shim'),'-I'+str(r/'test/native_settings_worker_shim'),'-c',r/'src/ports/esp32s3/NativeSettingsLifecycle.cpp','-o',o/'lifecycle.o'])
wi=['-I'+str(x) for x in [sys/'lib/PortableApps/include',sys/'lib/NativeApps/include',sys/'test/native_apps/stubs',sys/'lib/RemoteFiles/vendor/tinydtls_sha2',r/'test']]
run(['cc','-std=c11',*flags,*wi,'-DSYSTEM_WIFI_WORKFLOW_SOURCE="'+str(sys/'test/native_apps/wifi_workflow_test.c')+'"','-c',w/'tests/t051/wifi_controller.c','-o',o/'wifi.o'])
run(['cc','-std=c11',*flags,*wi,'-c',sys/'lib/RemoteFiles/vendor/tinydtls_sha2/sha2.c','-o',o/'sha2.o'])
source=['src/bootstrap/Json.cpp','src/bootstrap/Board.cpp','src/bootstrap/Runtime.cpp','src/runtime/streams/AppStreamSessions.cpp','src/runtime/streams/ProviderQueueHost.cpp','src/runtime/drivers/ProviderGraphV2.cpp','src/runtime/drivers/ProviderModuleV2.cpp','src/ports/esp32s3/CpuPort.cpp','src/runtime/storage/AppDataFiles.cpp','src/ports/esp32s3/NativeSettingsMaintenance.cpp','src/ports/esp32s3/NativeSettingsBootstrap.cpp']
run(['c++','-std=c++17',*flags,*inc,*selected,'-I'+str(r/'test/native_nvs_shim'),'-pthread','-rdynamic',*[r/s for s in source],o/'maintenance.cpp',o/'lifecycle.o',o/'wifi.o',o/'sha2.o','-ldl','-lcrypto','-Wl,--wrap=read,--wrap=write,--wrap=fsync,--wrap=close,--wrap=rename','-o',o/'test'])
board=json.loads((base/'store/board.json').read_text());(o/'board.json').write_text(json.dumps(board))
sd=json.loads((w/'drivers/storage_sdmmc/manifest.json').read_text());sd['requires'].append(dict(capability='platform.storage-worker',api=1));(o/'sd.json').write_text(json.dumps(sd))
grants=[dict(capability=c,api=1,instance_id=n) for c,n in [('storage.key-value',1),('storage.key-value.atomic',6),('storage.key-value.availability',6)]]
(o/'boot.json').write_text(json.dumps(dict(board='board.json',default_app='default.elf',provider_activation='demand',drivers=[dict(manifest='sd.json',instance_id=12)],installation=dict(volume_instance=12,grants=[]),app_capabilities=[dict(manifest='app.json',grants=grants)])))
(o/'app.json').write_text(json.dumps(dict(type='application',id='maintenance-test',version='1.0.0',architecture='xtensa-esp32s3',file_name='default.elf',entry='app_main',requires=[dict(capability=c,api=1) for c in ['storage.key-value','storage.key-value.atomic','storage.key-value.availability']])))
(o/'app.c').write_text('extern void test_maintenance_app(void); void app_main(void){test_maintenance_app();}\n');run(['cc','-shared','-fPIC',o/'app.c','-o',o/'default.elf'])
card=o/'card.img';card.unlink(missing_ok=True)
for case in ['wave-save','wave-reload','wave-final']:run([o/'test',o,case,o/'native'],env={**os.environ,'WAVE_CARD':str(card)},timeout=60)

card.unlink(missing_ok=True)
run([o/"test",o,"wave-first",o/"first-native"],env={**os.environ,"WAVE_CARD":str(card)},timeout=60)
