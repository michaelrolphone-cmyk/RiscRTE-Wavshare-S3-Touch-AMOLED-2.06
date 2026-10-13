"""Device-store composition of existing, unmodified capability providers."""
import json
import shutil
import os
import subprocess
import sys


def stage_watch_providers(*, build, store, boot, device, shared, controllers,
                          generic, temporal, system, utilities, runtime, compiler, components):
    def provider(directory, source, includes, instance=None, manifest=None, extra=(), policy=None, **options):
        target=store/directory
        build(source,target/'driver.elf',includes,'t5_driver_get',extra,**options)
        shutil.copy2(manifest or source.parent/'manifest.json',target/'manifest.json')
        row={'manifest':directory+'/manifest.json'}
        if instance is not None:row['instance_id']=instance
        if policy:row.update(policy)
        boot['drivers'].append(row)
    sdk=[shared/'sdk/driver',generic/'sdk/driver',shared/'sdk/app',shared/'include']
    provider('codec',device/'drivers/codec_es83xx/driver.c',[device/'include',*sdk],10)
    for directory,source in [('power-sleep','legacy_power_sleep'),('display-power','legacy_display_power')]:
        provider(directory,generic/('Drivers/'+source+'/driver.c'),sdk)
    for role in ('input','output'):
        provider('audio-'+role,generic/('Drivers/pcm_audio_'+role+'/driver.c'),sdk)
    for role,instance in [('wifi',15),('ble',16)]:
        provider(role,controllers/('drivers/twatch_'+role+'/driver.c'),
                 [controllers/'include',*sdk],instance)
    for directory,source in [('battery-telem','telemetry_battery'),('ble-telemetry','ble_telemetry'),
                             ('s3-radio-iq','s3_radio_iq_v1')]:
        owner=temporal if source=='s3_radio_iq_v1' else generic
        provider(directory,owner/('Drivers/'+source+'/driver.c'),[owner/'sdk/driver'] if source=='s3_radio_iq_v1' else sdk,
                 extra=['-Wl,--exclude-libs,ALL'] if source=='s3_radio_iq_v1' else [],
                 version_script=source!='s3_radio_iq_v1',section_gc=source!='s3_radio_iq_v1')
    provider('ble-sensors',temporal/'Drivers/ble_sensors/driver.c',[temporal/'sdk/driver'],
             extra=['-Wl,--exclude-libs,ALL'])
    # Reuse the exact NimBLE recipe, including source inventory and export
    # checks; compiling its vendor sources as a single generic TU is incorrect.
    subprocess.run([sys.executable,str(temporal/'scripts/build_ble_hid.py')],check=True,
                   env={**os.environ,'NATIVE_DRIVER_CC':str(compiler)})
    hid=temporal/'dist/ble-hid';target=store/'ble-hid';target.mkdir()
    for name in ('driver.elf','manifest.json'):shutil.copy2(hid/name,target/name)
    from compact_current_elf import compact
    compact(target/'driver.elf',str(compiler),debug_path=components/'debug/ble-hid.elf')
    evidence=components/'ble-hid';evidence.mkdir()
    for name in ('build-record.json','NimBLE-LICENSE','NimBLE-NOTICE','NimBLE-SOURCE.json','TinyCrypt-LICENSE'):
        shutil.copy2(hid/name,evidence/name)
    boot['drivers'].append({'manifest':'ble-hid/manifest.json','key_value':[
        {'key':key,'namespace':10,'access':'read-write'}
        for key in ('hid_ours','hid_peer','hid_ccc','hid_identity')]})
    service_sdk=[utilities/'lib/Alarm/include',utilities/'lib/Contexts/include',
                 utilities/'lib/Broadcast/include',utilities/'Apps',
                 runtime/'sdk/driver',runtime/'sdk/app',system/'lib/PortableApps/include',generic/'sdk/driver']
    alarm=utilities/'Services/alarm_service'
    keys=json.loads((alarm/'points-storage-policy.example.json').read_text())
    policy={'key_value':[dict(key=key,**value) for key,value in keys.items()]}
    provider('alarm-service',alarm/'service.c',service_sdk,
             manifest=alarm/'watch-clock-change-manifest.json',policy=policy,
             extra=['-DPOINTS_IN_TIME_SERVICE','-DPORTABLE_RTC_UTC8_DENVER',
                    '-DALARM_VOLUME_CONTROL','-DALARM_DND_CONTROL','-DALARM_CLOCK_CHANGE_CONTROL'])
    provider('broadcast',utilities/'Services/telemetry_broadcast/service.c',
             [utilities/'lib/Broadcast/include',system/'lib/PortableApps/include',generic/'sdk/driver'])
    provider('contexts',utilities/'Services/contexts/service.c',
             [utilities/'Apps',utilities/'lib/Contexts/include',temporal/'sdk/driver',system/'lib/PortableApps/include'],
             extra=[system/'lib/NativeApps/src/SingleFloatDivisionCompat.c'],section_gc=False)
    # Chip-specific absence is expressed by the product graph, never fake
    # providers or model branches in shared applications.
    return {'physical_instances':[10,15,16],
            'services':[('alarm.service',1,0),('telemetry.broadcast',1,0),('contexts.service',1,0)],
            'foreground':[('input.power-key',1,0),('power.sleep',1,0),('display.power',1,0),('board.battery',1,4),('storage.key-value',1,1),
                          ('net.wifi',1,15),('bluetooth.hci',1,16),('motion.accel',1,7)],
            'unavailable_hardware':['radio.lora','infrared.output']}
