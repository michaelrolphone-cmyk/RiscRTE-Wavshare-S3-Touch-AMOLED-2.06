"""Compose portable applications using their recorded Watch source owners.

The UI adapter and generic bridges are independently pinned by the caller.
Sources are never replaced by whichever System checkout happens to be newest.
"""
import hashlib
import json
import shutil
import sys

READY_APPS=('battery','calculator','stopwatch','alarms','countdown','wifi_settings','frequency_generator','points_in_time','ble_scanner','ble_touchpad','ble_buttons')

def stage_ready_apps(*,build,application,store,components,dirs,catalog,alarm_profile,closure):
    sys.path.insert(0,str(dirs['controllers']/'scripts'))
    from build_contexts_cohort import definitions
    from build_current_apps import application_inputs
    shared=dirs['bridge_shared']; ui=dirs['watch_system']; utilities=dirs['utilities']
    repos={'system-apps':ui,'utilities':utilities,'runtime':dirs['runtime']}
    # application_inputs uses this name for non-launcher clients. Keep the real
    # catalog because Contexts quick actions can launch installed applications.
    (components/'empty_catalog.c').write_bytes(catalog.read_bytes())
    receipts={}
    # Preserve the recorded Productivity color recipe: no paper provider exists
    # in this product, and no app-side model detection is introduced.
    shutil.copy2(dirs['modern_system']/'Apps/PaperPresentation.h',components/'PaperPresentation.h')
    paper=components/'paper-absent.c'
    paper.write_text('#include "PaperPresentation.h"\nconst paper_presentation *paper_presentation_get(void){return 0;}\n')
    for name in READY_APPS:
        owner_key='system' if name=='wifi_settings' else 'productivity' if name=='points_in_time' else 'utilities'
        if name=='ble_scanner':owner_key='scanner_utilities'
        owner=dirs[owner_key]
        source=owner/'Apps'/(name+'.c')
        original=json.loads((owner/'Apps'/(name+'.json')).read_text())
        flags=[f for f in definitions(name,original['version'],shared) if f!='-flto']
        flags+=['-DPORTABLE_NAVIGATION_RETENTION','-DPORTABLE_ASYNC_RGB565','-DPORTABLE_WATCH_NATIVE_HEIGHT','-include',str(alarm_profile)]
        sources,includes,_=application_inputs(name,source,repos,shared,components,'runtime-features')
        includes += [utilities/'lib/Contexts/include',components]
        if name=='points_in_time':
            sources.append(paper)
        build(sources[0],store/(name+'.elf'),includes,'app_main; app_module_init; app_module_fini',[*sources[1:],*flags])
        grants=[('display.output',1,5),('input.touch.raw',1,6),('rtc.clock',2,8)]
        # The first namespace is the app's default acquisition (instance 0).
        # Preference namespace 1 remains separately available to shared chrome.
        namespace={'stopwatch':2,'alarms':3,'countdown':3,'wifi_settings':6,'points_in_time':5,'ble_buttons':11}.get(name)
        if namespace:grants.append(('storage.key-value',1,namespace))
        grants+=closure['services']+closure['foreground']
        if name=='frequency_generator':grants.append(('audio.output',1,0))
        if name=='ble_scanner':grants.append(('bluetooth.sensors',1,0))
        if name in ('ble_touchpad','ble_buttons'):grants.append(('bluetooth.hid',1,0))
        application(name,{'type':'application','id':name,'version':original['version'],
                         'architecture':'xtensa-esp32s3','entry':'app_main'},grants)
        receipts[name]={'source':str(source.relative_to(owner)),
                        'source_owner':owner_key,
                        'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
                        'defines':flags,'grants':grants,
                        'elf_sha256':hashlib.sha256((store/(name+'.elf')).read_bytes()).hexdigest(),
                        'hardware_verified':False}
    (components/'ready-apps.json').write_text(json.dumps(receipts,indent=2)+'\n')
    return READY_APPS
