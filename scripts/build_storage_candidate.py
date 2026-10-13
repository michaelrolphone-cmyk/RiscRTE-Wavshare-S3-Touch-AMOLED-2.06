#!/usr/bin/env python3
"""Stage real app-data/scene dependencies beside the immutable 0.1.8 store.

This is a source-composition checkpoint, not a flashable image. Shared catalog
integration and whole-store/native admission must precede image assembly.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('baseline', 'receipt', 'runtime', 'controllers', 'modern-system',
                 'ui-system', 'utilities', 'service-utilities', 'productivity',
                 'bridges', 'shared', 'cc', 'output'):
        parser.add_argument('--' + name, required=True, type=Path)
    parser.add_argument('--preserved-baseline', type=Path)
    parser.add_argument('--contexts', action='store_true')
    parser.add_argument('--apps', nargs='+', choices=('timecard','audio_spectrum','waterfall'), default=['timecard','audio_spectrum','waterfall'])
    a = parser.parse_args()
    for name, value in vars(a).items():
        if isinstance(value, Path):
            setattr(a, name, value.resolve())
    if a.output.exists():
        raise ValueError('Use a new candidate output; no baseline overwrite')
    receipt = json.loads(a.receipt.read_text())
    if receipt['sha256'] != '7ce14678fb8e5c113ad55d96382e94270220088cb8640a5568faf2b9a99ea89a':
        raise ValueError('Wrong delivered baseline receipt')
    actual = {p.relative_to(a.baseline).as_posix(): {'bytes': p.stat().st_size, 'sha256': sha(p)}
              for p in a.baseline.rglob('*') if p.is_file()}
    if actual != receipt['store_files']:
        raise ValueError('Baseline store differs from delivered receipt')
    source_pins = {}
    for name, key in [('controllers','controllers'), ('modern_system','modern_system'),
                      ('ui_system','watch_system'), ('utilities','utilities'),
                      ('service_utilities','service_utilities'), ('productivity','productivity'),
                      ('bridges','bridge_shared'), ('shared','shared')]:
        source = getattr(a, name)
        head = subprocess.check_output(['git','-C',str(source),'rev-parse','HEAD'],text=True).strip()
        if head != receipt['source_pins'][key] or subprocess.check_output(['git','-C',str(source),'status','--porcelain','--untracked-files=no'],text=True).strip():
            raise ValueError('Source pin or tracked source differs: '+name)
        source_pins[name] = head
    a.output.mkdir(parents=True)
    store = a.output / 'store'
    shutil.copytree(a.baseline, store)
    components = a.output / 'components'
    components.mkdir()
    boot = json.loads((store / 'boot.json').read_text())
    sys.path.insert(0, str(a.controllers / 'scripts'))
    sys.path.insert(0, str(a.shared / 'scripts'))
    from compact_current_elf import compact
    from normalize_xtensa_relocations import normalize
    from build_contexts_cohort import definitions
    from build_current_apps import application_inputs
    validator = components / 'validate-elf'
    subprocess.run(['cc', '-std=c11', '-I'+str(a.ui_system/'test/native_apps/stubs'),
                    '-I'+str(a.ui_system/'lib/elf_loader/include'),
                    str(a.ui_system/'lib/elf_loader/src/esp_elf_validate.c'),
                    str(a.ui_system/'test/native_apps/validate_test.c'), '-o', str(validator)], check=True)
    receipts = {}

    def build(name, sources, includes, exports, flags=(), gc=True):
        elf = components / (name + '.elf')
        mapping = elf.with_suffix('.map')
        mapping.write_text('{ global: ' + '; '.join(exports) + '; local: *; };\n')
        command = [str(a.cc), '-std=c11', '-Os', '-fPIC', '-mtext-section-literals', '-mlongcalls',
                   '-fvisibility=hidden', '-ffreestanding', '-fno-builtin', '-nostdlib', '-nostartfiles',
                   '-shared', '-Wl,--no-relax', '-Wl,--hash-style=sysv', '-Wl,--version-script='+str(mapping),
                   '-Wall', '-Wextra', '-Werror', '-Wno-misleading-indentation']
        if gc:
            command += ['-ffunction-sections', '-fdata-sections', '-Wl,--gc-sections']
        command += [*flags, *['-I'+str(p) for p in includes], *map(str, sources), '-lgcc', '-o', str(elf)]
        subprocess.run(command, check=True)
        normalize(elf)
        compact(elf, str(a.cc), debug_path=components/'debug'/(name+'.elf'))
        subprocess.run([str(validator), str(elf)], check=True)
        receipts[name] = {'sources': {str(p): sha(p) for p in sources}, 'command': command,
                          'bytes': elf.stat().st_size, 'sha256': sha(elf), 'hardware_verified': False}
        return elf

    # Universal original catalog for compilation only. No product availability
    # rewriting. Shared-owner app.catalog integration must replace this input
    # before this candidate can be delivered.
    shutil.copy2(a.ui_system/'test/native_apps/fixtures/watch_springboard_catalog_23.c', components/'empty_catalog.c')
    alarm = components/'watch-alarm-profile.h'
    alarm.write_text('#include "'+str(a.service_utilities/'lib/Alarm/include/AlarmServiceV1.h')+'"\n'
                     '#define ALARM_MODE_VISUAL 0u\n'
                     'static inline uint32_t alarm_service_output_modes(const alarm_service_v1*s){return s?ALARM_MODE_BOTH:ALARM_MODE_VISUAL;}\n')
    shutil.copy2(a.modern_system/'Apps/PaperPresentation.h', components/'PaperPresentation.h')
    paper = components/'paper-absent.c'
    paper.write_text('#include "PaperPresentation.h"\nconst paper_presentation *paper_presentation_get(void){return 0;}\n')
    repos = {'system-apps': a.ui_system, 'utilities': a.utilities, 'productivity': a.productivity, 'runtime': a.runtime}
    common_grants = next(row['grants'] for row in boot['app_capabilities'] if row['manifest']=='battery.json')
    for name, namespace, kv in (('timecard',1,1), ('audio_spectrum',2,7), ('waterfall',3,13)):
        if name not in a.apps:
            continue
        owner = a.productivity if name=='timecard' else a.utilities
        source = owner/'Apps'/('timecard_portable.c' if name=='timecard' else name+'.c')
        manifest = json.loads((owner/'Apps'/('native' if name=='timecard' else '')/(name+'.json')).read_text())
        flags = [f for f in definitions(name, manifest['version'], a.bridges) if f!='-flto']
        flags += ['-DPORTABLE_NAVIGATION_RETENTION', '-DPORTABLE_ASYNC_RGB565', '-DPORTABLE_WATCH_NATIVE_HEIGHT', '-include', str(alarm)]
        sources, includes, _ = application_inputs(name, source, repos, a.bridges, components, 'runtime-features')
        includes += [a.utilities/'lib/Contexts/include', components]
        if name=='timecard':
            sources.append(paper)
        elf = build(name, sources, includes, ['app_main','app_module_init','app_module_fini'], flags, gc=name=='timecard')
        shutil.copy2(elf, store/(name+'.elf'))
        grants = [{'capability':'storage.app-data','api':1,'instance_id':namespace},
                  {'capability':'storage.key-value','api':1 if name=='timecard' else 2,'instance_id':kv}]
        grants += common_grants
        if name=='audio_spectrum':
            grants.append({'capability':'audio.input','api':1,'instance_id':0})
        if name=='waterfall':
            grants.append({'capability':'radio.iq','api':1,'instance_id':0})
        grants = list({(g['capability'],g['api'],g['instance_id']):g for g in grants}.values())
        declared = list({(g['capability'],g['api']): {'capability':g['capability'],'api':g['api']} for g in grants}.values())
        write(store/(name+'.json'), {'type':'application','id':name,'version':manifest['version'],
              'architecture':'xtensa-esp32s3','entry':'app_main','file_name':name+'.elf','requires':declared})
        boot['app_capabilities'].append({'manifest':name+'.json','grants':grants})
    sdk = load('storage_candidate_sdk', a.modern_system/'scripts/scene_sdk.py')
    include = sdk.stage_sdk(a.runtime, a.modern_system, components/'scene-sdk')
    for name in ('PortableTimeZone.h','PortableTimeZonePreference.h','PortableRtcClock.h','PortableTime.h'):
        shutil.copy2(a.modern_system/'lib/PortableApps/include'/name, include/name)
    shutil.copytree(a.modern_system/'lib/PortableApps/time', include.parent/'time')
    for name, folder, manifest_name, sources, flags in (
        ('scene-profile','scene_profile','compact-color.json',[a.modern_system/'Services/scene_profile/profile.c'],[]),
        ('ui-scene','scene_host','manifest.json',[a.modern_system/'Services/scene_host/host.c'],[]),
        ('civil-clock','civil_clock','watch.json',[a.modern_system/'Services/civil_clock/clock.c',
         a.modern_system/'lib/PortableApps/src/PortableTimeZone.c',a.modern_system/'lib/PortableApps/src/PortableTimeZoneCatalog.c'],['-DPORTABLE_RTC_UTC8_DENVER','-DCIVIL_CLOCK_ID="civil-clock-watch"'])):
        manifest = json.loads((a.modern_system/'Services'/folder/manifest_name).read_text())
        if name=='ui-scene':
            # Existing Watch raw-touch recipe: navigation is optional in host.c.
            manifest['requires'] = [r for r in manifest['requires'] if r['capability']!='input.navigation']
        elf = build(name, sources, [include], ['t5_driver_get'], flags)
        target = store/name
        target.mkdir()
        shutil.copy2(elf, target/'driver.elf')
        write(target/'manifest.json', manifest)
        boot['drivers'].append({'manifest':name+'/manifest.json'})
    if a.preserved_baseline:
        # Hashes from the delivered 1.1.5 immutable recovery receipt.
        preserved = {'lists.elf':'79dcedcce8ea351e9ae16d4745aee5311f72832e0d8d71841a14b7468185d9da',
                     'lists.json':'2a7b4b0401320e8b6fa98631bf96005c8efbeaea47e99223b8c91d0096bb6bf9',
                     'model_viewer.elf':'24b73fff728355ab88e5b34f9eae1caeb9442bbbc36240bd6bc8c29f0708fed0',
                     'model_viewer.json':'8a6addf7d89da6d3135497c8ec22b16280e093c68915a8546a36902346d2cffc'}
        if sha(a.preserved_baseline/'boot.json')!='b8e7b00f14915b83dbf7047b9a10e2880e48eaaf9a909b45ebd27e98d4e3a2ac':
            raise ValueError('Qualified baseline policy differs')
        old_boot = json.loads((a.preserved_baseline/'boot.json').read_text())
        for name, expected in preserved.items():
            path = a.preserved_baseline/name
            if sha(path)!=expected:
                raise ValueError('Protected app artifact differs: '+name)
            shutil.copy2(path,store/name)
        for name in ('lists','model_viewer'):
            boot['app_capabilities'].append(next(row for row in old_boot['app_capabilities'] if row['manifest']==name+'.json'))
            receipts[name]={'reused_from':'qualified Watch 1.1.5', 'bytes':(store/(name+'.elf')).stat().st_size,
                            'sha256':sha(store/(name+'.elf')), 'hardware_verified':False}
    if a.contexts:
        if not a.preserved_baseline:
            raise ValueError('Contexts needs its qualified file and namespace policy')
        helper = load('candidate_contexts_builder', a.utilities/'scripts/build_contexts_scene.py')
        ctx_include = helper.stage(a.runtime, a.modern_system, components/'contexts-sdk')
        manifest = json.loads((a.utilities/'Apps/contexts-scene.json').read_text())
        manifest = {k:v for k,v in manifest.items() if k in ('type','id','version','architecture','file_name','entry','requires','display_name','icon')}
        elf = build('contexts-app', [a.utilities/'Apps/contexts.c',components/'empty_catalog.c'], [ctx_include],
                    ['app_main','risc_resident_app_descriptor_v1'],
                    ['-include',str(a.shared/'apps/clock/faces/ContextsFaces.h')], gc=False)
        shutil.copy2(elf,store/'contexts.elf')
        write(store/'contexts.json',manifest)
        boot['app_capabilities'].append(next(row for row in old_boot['app_capabilities'] if row['manifest']=='contexts.json'))
    write(store/'boot.json', boot)
    write(a.output/'composition.json', {'schema':1,'baseline':receipt['device_commit'],
          'runtime_source':subprocess.check_output(['git','-C',str(a.runtime),'rev-parse','HEAD'],text=True).strip(),
          'source_pins':source_pins,'selected_apps':a.apps,'components':receipts,'flashable':False,'whole_store_admission':False,
          'pending':['shared runtime-derived catalog','remaining files/sharing/update composition','native admission and image assembly'],
          'hardware_verified':False})


if __name__ == '__main__':
    main()
