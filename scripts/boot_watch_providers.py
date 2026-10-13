"""Device-store composition of existing, unmodified capability providers."""
import json
import shutil


def stage_watch_providers(*, build, store, boot, device, shared, controllers,
                          generic, system, utilities, runtime):
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
    for role in ('input','output'):
        provider('audio-'+role,generic/('Drivers/pcm_audio_'+role+'/driver.c'),sdk)
    for role,instance in [('wifi',15),('ble',16)]:
        provider(role,controllers/('drivers/twatch_'+role+'/driver.c'),
                 [controllers/'include',*sdk],instance)
    for directory,source in [('battery-telem','telemetry_battery'),('ble-telemetry','ble_telemetry'),
                             ('s3-radio-iq','s3_radio_iq_v1')]:
        provider(directory,generic/('Drivers/'+source+'/driver.c'),[generic/'sdk/driver'] if source=='s3_radio_iq_v1' else sdk,
                 extra=['-Wl,--exclude-libs,ALL'] if source=='s3_radio_iq_v1' else [],
                 version_script=source!='s3_radio_iq_v1',section_gc=source!='s3_radio_iq_v1')
    service_sdk=[utilities/'lib/Alarm/include',utilities/'lib/Contexts/include',
                 utilities/'lib/Broadcast/include',utilities/'Apps',
                 runtime/'sdk/driver',runtime/'sdk/app',generic/'sdk/driver',system/'lib/PortableApps/include']
    alarm=utilities/'Services/alarm_service'
    keys=json.loads((alarm/'points-storage-policy.example.json').read_text())
    policy={'key_value':[dict(key=key,**value) for key,value in keys.items()]}
    provider('alarm-service',alarm/'service.c',service_sdk,
             manifest=alarm/'watch-clock-change-manifest.json',policy=policy,
             extra=['-DPOINTS_IN_TIME_SERVICE','-DPORTABLE_RTC_UTC8_DENVER',
                    '-DALARM_VOLUME_CONTROL','-DALARM_DND_CONTROL','-DALARM_CLOCK_CHANGE_CONTROL'])
    provider('broadcast',utilities/'Services/telemetry_broadcast/service.c',service_sdk)
    provider('contexts',utilities/'Services/contexts/service.c',service_sdk,
             extra=[system/'lib/NativeApps/src/SingleFloatDivisionCompat.c'])
    # Chip-specific absence is expressed by the product graph, never fake
    # providers or model branches in shared applications.
    return {'physical_instances':[10,15,16],
            'services':[('alarm.service',1,0),('telemetry.broadcast',1,0),('contexts.service',1,0)],
            'foreground':[('board.battery',1,4),('storage.key-value',1,1),
                          ('net.wifi',1,15),('bluetooth.hci',1,16),('motion.accel',1,7)],
            'unavailable_hardware':['radio.lora','infrared.output']}
