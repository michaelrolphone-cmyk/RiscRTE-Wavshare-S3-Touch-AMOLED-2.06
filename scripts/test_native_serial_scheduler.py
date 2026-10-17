#!/usr/bin/env python3
"""Actual Runtime/CpuPort/native settings/Wave SD serial admission regression."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def qualify(runtime, sdk, output, expect, sanitize='both'):
    assert expect in ('baseline', 'fixed')
    assert sanitize in ('none', 'address,undefined', 'both')
    output.mkdir(parents=True, exist_ok=True)
    fixture = ROOT / 'tests/serial_native_scheduler'
    dependencies = {Path(__file__).resolve(), fixture/'prepare.py', fixture/'sd_fixture.c'}
    receipt = dict(schema=1, expectation=expect, hardware_tested=False,
        target_instructions_executed=False, leak_sanitizer=False,
        scope='Production Runtime, serial endpoint, RuntimeFiles, native settings lifecycle/maintenance, CpuPort and Wave SD/FatFs. Modeled hardware sectors, NVS and deterministic worker scheduling. No production Home instructions or complete observed generic barrier cause claim.',
        runtime_commit=subprocess.check_output(['git','-C',str(runtime),'rev-parse','HEAD'],text=True).strip(),
        runtime_dirty=bool(subprocess.check_output(['git','-C',str(runtime),'status','--porcelain'])),
        compilations=[], cases=[])
    selected = ['-DRISC_NATIVE_SERIAL_FILES=1','-DRISC_NATIVE_SETTINGS_PORT_SELECTED=1',
        '-DRISC_NATIVE_SETTINGS_NAMESPACE_MASK=3','-DRISC_NATIVE_SETTINGS_FRESH_INTERNAL_FALLBACK=1',
        '-DRISC_NATIVE_SETTINGS_LIFECYCLE=1','-DRISC_NATIVE_SETTINGS_WORKER=1',
        '-DRISC_RUNTIME_ATOMIC_KEY_VALUE=1','-DRISC_NATIVE_STORAGE_CUSTODY=1']
    modes = ('none','address,undefined') if sanitize == 'both' else (sanitize,)
    for mode in modes:
        label = 'normal' if mode == 'none' else 'sanitized'
        with tempfile.TemporaryDirectory(prefix='wave-native-serial-', dir=output.parent) as temp:
            work = Path(temp)
            subprocess.run([sys.executable,str(fixture/'prepare.py'),str(runtime),str(work),expect],check=True)
            for name in ('maintenance.cpp','native_sd_port_test.cpp'):
                (output/(label+'-'+name)).write_bytes((work/name).read_bytes())
            flags = ['-O0','-g1','-Wall','-Wextra','-Werror','-Wno-unused-function',
                '-Wno-unused-variable','-Wno-overflow','-Wno-misleading-indentation',
                '-Wno-missing-field-initializers','-fno-omit-frame-pointer']
            if mode != 'none':
                flags += ['-fsanitize='+mode,'-fno-sanitize-recover=all']
            inc = ['-I'+str(x) for x in (sdk,ROOT/'include',work,runtime,runtime/'src',
                runtime/'test',runtime/'test/drivers/stubs')]
            inc += ['-isystem',str(runtime/'lib/ArduinoJson/src')]
            commands = []
            def run(command):
                command = list(map(str,command)); commands.append(command)
                result = subprocess.run(command,capture_output=True,text=True)
                with (output/(label+'-compile.log')).open('a') as f:
                    f.write(json.dumps(command)+'\n'+result.stdout+result.stderr)
                if result.returncode: print(result.stdout+result.stderr,flush=True)
                result.check_returncode()
            def compile_one(language, source, extra, name):
                obj, dep = work/(name+'.o'), work/(name+'.d')
                run([language,'-std=c11' if language=='cc' else '-std=c++17',*flags,*inc,
                    *extra,'-MMD','-MF',dep,'-c',source,'-o',obj])
                for token in dep.read_text().replace('\\\n',' ').split(':',1)[1].split():
                    path = Path(token).resolve()
                    if not path.is_relative_to(work): dependencies.add(path)
                return obj
            provider = [compile_one('cc',source,['-fPIC'], 'provider-'+str(i))
                for i,source in enumerate((fixture/'sd_fixture.c',ROOT/'lib/storage_fatfs/fatfs/ff.c',
                                          ROOT/'lib/storage_fatfs/fatfs/ffunicode.c'))]
            run(['cc',*flags,'-shared',*provider,'-o',work/'driver.elf'])
            lifecycle = compile_one('c++',runtime/'src/ports/esp32s3/NativeSettingsLifecycle.cpp',
                [*selected,'-DESP_PLATFORM','-I'+str(runtime/'test/native_nvs_shim'),
                 '-I'+str(runtime/'test/native_settings_worker_shim')],'lifecycle')
            sources = ['src/runtime/serial/Files.cpp','src/bootstrap/Json.cpp','src/bootstrap/Board.cpp',
                'src/bootstrap/Runtime.cpp','src/runtime/streams/AppStreamSessions.cpp',
                'src/runtime/streams/ProviderQueueHost.cpp','src/runtime/drivers/ProviderGraphV2.cpp',
                'src/runtime/drivers/ProviderModuleV2.cpp','src/ports/esp32s3/CpuPort.cpp',
                'src/runtime/storage/AppDataFiles.cpp','src/ports/esp32s3/NativeSettingsMaintenance.cpp',
                'src/ports/esp32s3/NativeSettingsBootstrap.cpp']
            objects = [compile_one('c++',source,[*selected,'-I'+str(runtime/'test/native_nvs_shim'),'-pthread'],
                                   'runtime-'+str(i))
                       for i,source in enumerate([*[runtime/s for s in sources],work/'maintenance.cpp'])]
            run(['c++',*flags,'-pthread','-rdynamic',*objects,lifecycle,'-ldl','-lcrypto',
                 '-Wl,--wrap=read,--wrap=write,--wrap=fsync,--wrap=close,--wrap=rename','-o',work/'test'])
            (work/'board.json').write_bytes((ROOT/'hardware/board.json').read_bytes())
            sd = json.loads((ROOT/'drivers/storage_sdmmc/manifest.json').read_bytes())
            sd['requires'].append(dict(capability='platform.storage-worker',api=1))
            (work/'sd.json').write_text(json.dumps(sd))
            capabilities = ['storage.key-value','storage.key-value.atomic','storage.key-value.availability']
            grants = [dict(capability=c,api=1,instance_id=n) for c,n in
                [('storage.key-value',1),('storage.key-value.atomic',1),('storage.key-value.atomic',6),
                 ('storage.key-value.availability',1),('storage.key-value.availability',6)]]
            (work/'boot.json').write_text(json.dumps(dict(board='board.json',default_app='default.elf',
                provider_activation='demand',drivers=[dict(manifest='sd.json',instance_id=12)],
                installation=dict(volume_instance=12,grants=[]),app_capabilities=[dict(manifest='app.json',grants=grants)])))
            (work/'app.json').write_text(json.dumps(dict(type='application',id='maintenance-test',version='1.0.0',
                architecture='xtensa-esp32s3',file_name='default.elf',entry='app_main',
                requires=[dict(capability=c,api=1) for c in capabilities])))
            (work/'app.c').write_text('extern void test_maintenance_app(void); void app_main(void){test_maintenance_app();}\n')
            run(['cc','-shared','-fPIC',work/'app.c','-o',work/'default.elf'])
            for case in ('unavailable-conflict','unavailable-return'):
                card = work/(case+'.card'); assert not card.exists()
                result = subprocess.run([str(work/'test'),str(work),case,str(work/case)],capture_output=True,
                    text=True,timeout=120,env={**os.environ,'WAVE_CARD':str(card),
                    'ASAN_OPTIONS':'detect_leaks=0','UBSAN_OPTIONS':'halt_on_error=1'})
                log = result.stdout + result.stderr
                (output/(label+'-'+case+'.log')).write_text(log)
                expected_return = 2 if expect=='baseline' and case=='unavailable-conflict' else 0
                assert result.returncode == expected_return, log
                assert 'runtime error:' not in log and 'ERROR: AddressSanitizer' not in log, log
                if expect == 'baseline':
                    assert ' -3 STAT 0 0' in log and 'session=1 volume=1 client_retained=0' in log, log
                    if case == 'unavailable-conflict':
                        assert ' -6 STAT 0 0' in log and 'session=0 volume=0 client_retained=1' in log, log
                        assert 'FINAL ran=0 retained=1 error=serial file custody retained; restart required' in log, log
                    else:
                        assert 'APP_RETURN_ACTIVE' in log and 'FINAL ran=1 retained=0 error= ' in log, log
                else:
                    assert 'checkpoint=1 continuing=1 discovering=1 pinned=1 session=1' in log, log
                    assert 'dispatch=3 wire=\n' in log and ' -3 STAT' not in log and ' -6 STAT' not in log, log
                    assert 'FINAL ran=1 retained=0 error= lifecycle_retained=0 exit_safe=1 pinned=0 serial_retained=0' in log, log
                    if case == 'unavailable-conflict':
                        assert 'DEFERRED_RESPONSE rc=0 wire=RTEF1 12345678 4 0 STAT 6 4' in log, log
                        assert 'PROBE_END active=1 closed=1 continuing=0 exit=1 pinned=0' in log, log
                    else: assert 'APP_RETURN_ACTIVE' in log, log
                assert 'SERIAL_BEFORE command=STAT 12 continuing=1 discovering=1 pinned=1 session=1' in log, log
                if case=='unavailable-conflict' and expect=='baseline':
                    assert 'SERIAL_BEFORE command=STAT 12 continuing=1 discovering=1 pinned=1 session=0' in log, log
                if card.exists(): card.unlink()  # This case's fresh, disposable modeled card only.
                receipt['cases'].append(dict(build=label,case=case,returncode=result.returncode,
                    expected_returncode=expected_return,log_sha256=hashlib.sha256(log.encode()).hexdigest(),passed=True))
                print(label+' '+expect+' '+case+' PASS',flush=True)
            receipt['compilations'].append(dict(build=label,commands=commands))
    for path in (ROOT/'hardware/board.json',ROOT/'drivers/storage_sdmmc/manifest.json',
                 runtime/'test/native_sd_port_test.cpp',runtime/'test/native_settings_maintenance_test.cpp'):
        dependencies.add(path)
    receipt['input_sha256'] = {str(path):hashlib.sha256(path.read_bytes()).hexdigest() for path in sorted(dependencies)}
    receipt['passed'] = True
    (output/'qualification.json').write_text(json.dumps(receipt,indent=2)+'\n')
    return receipt


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('runtime','sdk','output'): parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--expect',choices=('baseline','fixed'),required=True)
    parser.add_argument('--sanitize',choices=('none','address,undefined','both'),default='both')
    args = parser.parse_args()
    for name in ('runtime','sdk','output'): setattr(args,name,getattr(args,name).resolve())
    qualify(**vars(args))
