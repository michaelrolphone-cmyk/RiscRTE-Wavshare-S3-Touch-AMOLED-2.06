#!/usr/bin/env python3
"""Build an offline first-boot store and a single flash image at address zero.

Uses a separately compiled, pinned native Runtime. No board-specific application
variant, radio credential, SD card, paired updater or automatic sleep is needed.
"""
import argparse,hashlib,json,shutil,struct,subprocess,sys,tempfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SIZE=0x800000
FS_OFFSET=0x310000
FS_SIZE=0x4f0000
TOOL_SHA='4ddf79a1ab9a3baf502cdb979bea7ed173bbe46727a9902649cc09e6a28a5ad2'
NAME='Waveshare-0.1.8-Home-0.15.0-boot-test-full-0x0.bin'
PINS={
 'runtime':'56036e51b34e2054600d4465554a101914dec7a4',
 'shared':'ec768c7fae6fdb484fef28c6ec87f129b0a7f585',
 'diagnostic_shared':'2d3df3d50647578987eb209bf7e2b8d722715d00',
 'home_system':'076f8da38f7dfebdfde6dd5d46e06446470fb828',
 'modern_system':'1aaf53e23ca9651a5cf9d1debe44941c9d7d0e58',
 'productivity':'0b8667d64e76a6b4bbd325a1c963405f3af57404',
 'scanner_utilities':'377d471d284cf18e13927481362d011bc981dfee',
 'bridge_shared':'6e82fdcaec0b73ed700d2104cfb4d94f011c19d4',
 'controllers':'851b8998e804c57b2c9f42d9f8fd0a69e79f2b41',
 'generic':'422e1e81a498fb6bdab9abf086325afc05a532dc',
 'system':'14762601b3fa7bbeeac5ed565a6825534bf74dca',
 'utilities':'fc0bdbbbc600ce891e60c44d091fce0586ade7d8',
 'service_utilities':'80efb298c9ca8d0f62f9a31840c9e51d380b40f6',
 'watch_system':'2c3f44dd773e27e3a142462088a96328119a79e7',
 'temporal':'aac1cb342696e96345d4546e2c69023834c6c8d4'}

def digest(data):return hashlib.sha256(data).hexdigest()
def json_write(path,value):
 path.parent.mkdir(parents=True,exist_ok=True)
 path.write_text(json.dumps(value,indent=2)+'\n')
def files(root):return {p.relative_to(root).as_posix():p.read_bytes() for p in root.rglob('*') if p.is_file()}
def run(*command,**kw):return subprocess.run(list(map(str,command)),check=True,**kw)
def main():
 p=argparse.ArgumentParser(description=__doc__)
 for name in (*PINS,'native','cc','mkspiffs','output'):
  p.add_argument('--'+name,required=True,type=Path)
 p.add_argument('--device',type=Path,default=ROOT)
 a=p.parse_args()
 dirs={k:getattr(a,k).resolve() for k in PINS}
 for name,expected in PINS.items():
  actual=subprocess.check_output(['git','-C',str(dirs[name]),'rev-parse','HEAD'],text=True).strip()
  if actual!=expected:raise ValueError(f'{name} source is {actual}, expected {expected}')
 if digest(a.mkspiffs.read_bytes())!=TOOL_SHA:raise ValueError('Wrong Arduino ESP32 SPIFFS tool')
 if a.output.exists() and any(a.output.iterdir()):raise ValueError('Use a new empty output directory')
 out=a.output.resolve();out.mkdir(parents=True,exist_ok=True)
 store=out/'store';store.mkdir();components=out/'components';device=a.device.resolve()
 S=dirs['shared'];T=dirs['controllers'];G=dirs['generic'];N=dirs['runtime'];cc=a.cc.resolve()
 sys.path.insert(0,str(S/'scripts'))
 from compact_current_elf import compact
 from normalize_xtensa_relocations import normalize
 home_receipt=json.loads((device/'profiles/home-artifact.json').read_text())
 for role,key in [('shared','shared_commit'),('home_system','system_commit'),('utilities','utilities_commit')]:
  if PINS[role]!=home_receipt[key]:raise ValueError('Public Home receipt source mismatch: '+role)
 run(sys.executable,S/'scripts/build.py','--system',dirs['home_system'],'--utilities',dirs['utilities'],'--cc',cc,'--output',components)
 for name,wanted in home_receipt['files'].items():
  raw=(components/name).read_bytes()
  if len(raw)!=wanted['bytes'] or digest(raw)!=wanted['sha256']:raise ValueError('Shared app identity mismatch: '+name)
 validator=components/'validate-elf'
 def build(source,target,includes,symbol,extra=(),version_script=True,section_gc=True):
  target.parent.mkdir(parents=True,exist_ok=True)
  version=target.with_suffix('.map');version.write_text('{ global: '+symbol+'; local: *; };\n')
  run(cc,'-std=c11','-Os','-fPIC','-mtext-section-literals','-mlongcalls','-fvisibility=hidden','-ffreestanding','-fno-builtin','-nostdlib','-nostartfiles','-shared',*(['-Wl,--gc-sections'] if section_gc else []),'-Wl,--no-relax','-Wl,--hash-style=sysv',*(['-ffunction-sections','-fdata-sections'] if section_gc else []),*(['-Wl,--version-script='+str(version)] if version_script else []),'-Wall','-Wextra','-Werror','-Wno-misleading-indentation',*['-I'+str(v) for v in includes],*(['-DCO5300_BOOT_PROBE=1'] if source.parent.name=='panel_co5300' else []),source,*extra,'-lgcc','-o',target)
  normalize(target);compact(target,str(cc),debug_path=components/'debug'/(target.parent.name+'-'+target.name))
  run(validator,target);version.unlink()
 boot={'board':'board.json','default_app':'default.elf','provider_activation':'demand-retained','drivers':[],'app_capabilities':[]}
 for name,instance,source in [('gpio',1,T/'drivers/twatch_gpio/driver.c'),('i2c',2,T/'drivers/twatch_i2c/i2c_main.c')]:
  build(source,store/name/'driver.elf',[S/'sdk/driver',T/'include'],'t5_driver_get')
  shutil.copy2(source.parent/'manifest.json',store/name/'manifest.json')
  boot['drivers'].append({'manifest':name+'/manifest.json','instance_id':instance})
 for name,folder,instance in [('battery','power_axp2101',4),('display','panel_vendor',5),('touch','touch_ft3168',6),('motion','motion_qmi8658',7),('rtc','rtc_pcf85063',8),('haptic','haptic_gpio',9)]:
  source=device/'drivers'/folder
  build(source/'driver.c',store/name/'driver.elf',[device/'include',S/'sdk/driver',S/'sdk/app',S/'include'],'t5_driver_get')
  shutil.copy2(source/'manifest.json',store/name/'manifest.json')
  boot['drivers'].append({'manifest':name+'/manifest.json','instance_id':instance})
 source=device/'drivers/display_rail_axp2101'
 build(source/'driver.c',store/'rail/driver.elf',[device/'include',S/'sdk/driver',S/'sdk/app',S/'include'],'t5_driver_get')
 shutil.copy2(source/'manifest.json',store/'rail/manifest.json')
 boot['drivers'].append({'manifest':'rail/manifest.json','instance_id':13})
 build(G/'Drivers/legacy_power_key/driver.c',store/'powerkey/driver.elf',[G/'sdk/driver',S/'sdk/driver'],'t5_driver_get')
 shutil.copy2(G/'Drivers/legacy_power_key/manifest.json',store/'powerkey/manifest.json')
 boot['drivers'].append({'manifest':'powerkey/manifest.json'})
 from boot_watch_providers import stage_watch_providers
 closure=stage_watch_providers(build=build,store=store,boot=boot,device=device,shared=S,controllers=T,
  generic=G,temporal=dirs['temporal'],system=dirs['system'],utilities=dirs['service_utilities'],runtime=N,compiler=cc,components=components)
 board=json.loads((device/'hardware/board.json').read_text())
 board['devices']=[d for d in board['devices'] if d['instance_id'] in (1,2,4,5,6,7,8,9,10,13,15,16)]
 json_write(store/'board.json',board)
 def application(name,manifest,grants):
  manifest['file_name']=name+'.elf'
  manifest['requires']=[{'capability':c,'api':v} for c,v in dict.fromkeys((c,v) for c,v,i in grants)]
  json_write(store/(name+'.json'),manifest)
  boot['app_capabilities'].append({'manifest':name+'.json','grants':[{'capability':c,'api':v,'instance_id':i} for c,v,i in grants]})
 base=[('display.output',1,5),('board.battery',1,4),('rtc.clock',2,8),('input.touch.raw',1,6),('input.power-key',1,0),('runtime.realtime-control',1,0),('storage.key-value',1,1),('storage.key-value',1,5)]
 base += closure['services']+[('power.sleep',1,0),('display.power',1,0),('net.wifi',1,15),('bluetooth.hci',1,16),('motion.accel',1,7)]
 for role in ('default','clock'):
  manifest=json.loads((S/'apps/clock'/(role+'.json')).read_text())
  if manifest['version']!='0.15.0':raise ValueError('First-boot Home fixes are absent')
  shutil.copy2(components/(role+'.elf'),store/(role+'.elf'))
  application(role,manifest,base+([('runtime.provider-promotion',1,0)] if role=='default' else []))
 # Keep diagnostics under their own name; never alias a launcher/settings entry.
 diagnostic=dirs['diagnostic_shared']
 build(diagnostic/'apps/bringup/main.c',store/'bringup.elf',[diagnostic/'sdk/app',diagnostic/'sdk/driver',diagnostic/'include'],'app_main',[diagnostic/'apps/clock/viewport.c'])
 diagnostics={'type':'application','id':'watch-bringup','version':'0.1.0','architecture':'xtensa-esp32s3','entry':'app_main'}
 grants=[('display.output',1,5),('input.touch.raw',1,6),('board.battery',1,4),('rtc.clock',2,8),('motion.accel',1,7),('haptic.effect',1,9)]
 application('bringup',diagnostics,grants)
 system=dirs['watch_system']
 bridges=dirs['bridge_shared']
 from boot_watch_apps import READY_APPS,stage_ready_apps
 catalog=components/'watch-tools-catalog.c'
 # Preserve the original ordered honeycomb catalog. Missing installed apps
 # remain explicitly incompatible until their qualified components are staged.
 catalog_source=(system/'test/native_apps/fixtures/watch_springboard_catalog_23.c').read_text()
 import re
 def catalog_availability(match):
  name=match.group(1)
  available=(store/name).is_file() or name=='settings.elf' or name.removesuffix('.elf') in READY_APPS
  return '.file_name="'+name+'"'+match.group(2)+'.compatible='+('true' if available else 'false')
 catalog.write_text(re.sub(r'\.file_name="([^"]+)"([^}]*?)\.compatible=true',catalog_availability,catalog_source))
 alarm_profile=components/'watch-alarm-profile.h'
 alarm_profile.write_text('#include "'+str(dirs['service_utilities']/'lib/Alarm/include/AlarmServiceV1.h')+'"\n'
  '#define ALARM_MODE_VISUAL 0u\n'
  'static inline uint32_t alarm_service_output_modes(const alarm_service_v1*s){return s?ALARM_MODE_BOTH:ALARM_MODE_VISUAL;}\n')
 for role,return_app in [('springboard','clock.elf'),('settings','springboard.elf')]:
  extra=[system/'lib/PortableApps/src/adapter.c',catalog,bridges/'apps/clock/portable_navigation.c',bridges/'apps/clock/portable_sleep.c',
   *[system/'lib/PortableApps/src'/n for n in ('quick_actions.c','quick_render.c','quick_session.c','quick_radios.c')],
   '-DPORTABLE_FORCE_FULL_FRAMES','-DPORTABLE_RTC_UTC8_DENVER','-DPORTABLE_NOVA_UI','-DPORTABLE_WATCH_NATIVE_HEIGHT','-DPORTABLE_ASYNC_RGB565',
   '-DPORTABLE_NAVIGATION_RETENTION','-DPORTABLE_INPUT_NAVIGATION','-DPORTABLE_INPUT_NAVIGATION_LOCAL','-DPORTABLE_APP_SLEEP_LOCAL',
   '-DPORTABLE_ALARM_CLIENT','-DPORTABLE_QUICK_ACTIONS','-DPORTABLE_QUICK_RADIOS','-DPORTABLE_MOTION_WAKE',
   '-DWATCH_ALARM_SLEEP_RESUME','-DPORTABLE_LOW_BATTERY','-DPORTABLE_BLE_BROADCAST','-DPORTABLE_CONTEXTS_CLIENT',
   '-include',str(S/'apps/clock/faces/ContextsFaces.h'),'-include',str(alarm_profile),'-DPORTABLE_RETURN_APP="'+return_app+'"']
  if role=='settings':extra+=['-DPORTABLE_SETTINGS_APP','-DPORTABLE_TAP_SETTINGS','-DPORTABLE_SLEEP_SETTINGS','-DPORTABLE_ALARM_SETTINGS','-DPORTABLE_SETTINGS_CLOCK_CHANGE_CONTROL']
  else:extra+=[system/'lib/NativeApps/src/SingleFloatDivisionCompat.c','-DPORTABLE_RETAINED_RGB565_HANDOFF','-DPORTABLE_HANDOFF_EAGER_MS=60','-DPORTABLE_CATALOG_LIMIT=23']
  build(system/'Apps'/(role+'.c'),store/(role+'.elf'),[dirs['service_utilities' if role=='settings' else 'utilities']/'lib/Alarm/include',dirs['service_utilities' if role=='settings' else 'utilities']/'lib/Contexts/include',system/'lib/PortableApps/include',system/'lib/NativeApps/include',bridges/'sdk/app',bridges/'sdk/driver',bridges/'include'],
    'app_main; app_module_init; app_module_fini',extra)
  manifest=json.loads((system/'Apps'/(role+'.json')).read_text())
  manifest={'type':'application','id':role,'version':manifest['version'],'architecture':'xtensa-esp32s3','entry':'app_main'}
  app_grants=[('display.output',1,5),('input.touch.raw',1,6),('rtc.clock',2,8)]
  app_grants += closure['services']+closure['foreground']
  application(role,manifest,app_grants)
 stage_ready_apps(build=build,application=application,store=store,components=components,
  dirs=dirs,catalog=catalog,alarm_profile=alarm_profile,closure=closure)
 # A launcher catalog entry must resolve to a real admitted application.
 for name in ('clock','settings','bringup',*READY_APPS):
  if not (store/(name+'.elf')).is_file() or not (store/(name+'.json')).is_file():raise ValueError('Unresolved launcher target: '+name)
 if (store/'springboard.elf').read_bytes()==(store/'bringup.elf').read_bytes():raise ValueError('Diagnostic aliased as Springboard')
 json_write(store/'boot.json',boot)
 from stage_product import app_bundle,stage
 app_files,_=app_bundle(components)
 staged,staging=stage(files(store),app_files,{},json.loads((device/'profiles/shared-home.json').read_bytes()),provider_capacity=40)
 for name,raw in staged.items():(store/name).write_bytes(raw)
 json_write(out/'shared-home-staging.json',staging)
 expected=files(store)
 if len(expected)!=62+2*len(READY_APPS) or sum(n.endswith('.elf') for n in expected)!=30+len(READY_APPS):raise ValueError('Unexpected boot inventory')
 if any(len(('/'+n).encode())>=32 for n in expected):raise ValueError('SPIFFS object path too long')
 def admit(path,label,sanitize=False):
  dest=out/label
  command=[sys.executable,ROOT/'scripts/validate_boot_test.py','--runtime',N,'--controllers',T,'--native-elf',a.native/'firmware.elf','--store',path,'--output',dest]
  if sanitize:command.append('--sanitize')
  result=subprocess.run(list(map(str,command)),text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
  (out/(label+'.log')).write_text(result.stdout)
  if result.returncode:raise RuntimeError(result.stdout[-8000:])
  print(result.stdout.strip(),flush=True)
  return dest/'admit'
 admit(store,'validation')
 checker=admit(store,'validation-sanitized',True)
 options=['-b','4096','-p','256','-s',str(FS_SIZE)]
 image=out/'bootfs.bin'
 run(a.mkspiffs,'-c',store,*options,image,stdout=subprocess.DEVNULL)
 sys.path.insert(0,str(N/'scripts'))
 from spiffs_image import read_image
 raw=image.read_bytes()
 if read_image(raw,FS_SIZE)!=expected:raise ValueError('Independent SPIFFS readback mismatch')
 unpacked=out/'readback';unpacked.mkdir()
 run(a.mkspiffs,'-u',unpacked,*options,image,stdout=subprocess.DEVNULL)
 if files(unpacked)!=expected:raise ValueError('SPIFFS implementation readback mismatch')
 run(checker,unpacked)
 refusals={}
 with tempfile.TemporaryDirectory() as tmp:
  damaged=Path(tmp)/'store';shutil.copytree(unpacked,damaged)
  cases=[('missing-display',lambda:(damaged/'display/driver.elf').unlink()),
         ('invalid-app-elf',lambda:(damaged/'default.elf').write_bytes(b'not an ELF')),
         ('missing-provider',lambda:(damaged/'touch/manifest.json').unlink()),
         ('missing-power-rail',lambda:(damaged/'rail/manifest.json').unlink())]
  for name,mutate in cases:
   mutate();result=subprocess.run([str(checker),str(damaged)],text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
   if result.returncode!=4:raise ValueError(f'Invalid store was not cleanly refused: {name}: {result.stdout}')
   refusals[name]=result.stdout.strip()
   shutil.rmtree(damaged);shutil.copytree(unpacked,damaged)
 json_write(out/'negative-admission.json',refusals)
 table=(a.native/'partitions.bin').read_bytes();parts={};verified=False
 for offset in range(0,len(table),32):
  entry=table[offset:offset+32]
  if entry[:2]==b'\xeb\xeb':
   if entry[16:32]!=hashlib.md5(table[:offset]).digest():raise ValueError('Partition MD5 mismatch')
   verified=True;break
  magic,kind,subtype,start,length,label,flags=struct.unpack('<HBBII16sI',entry)
  if magic!=0x50aa:raise ValueError('Invalid partition entry')
  parts[label.split(b'\0')[0].decode()]=(kind,subtype,start,length)
 if not verified or parts!={'nvs':(1,2,0x9000,0x6000),'factory':(0,0,0x10000,0x300000),'bootfs':(1,0x82,FS_OFFSET,FS_SIZE)}:raise ValueError('Unexpected partition layout')
 regions=[(0,'bootloader.bin',0x8000),(0x8000,'partitions.bin',0x1000),(0x10000,'firmware.bin',0x300000)]
 full=bytearray(b'\xff'*SIZE);records={}
 for offset,name,limit in regions:
  data=(a.native/name).read_bytes()
  if not data or len(data)>limit:raise ValueError(f'Invalid region size: {name}')
  if name!='partitions.bin' and (data[0]!=0xe9 or struct.unpack_from('<H',data,12)[0]!=9):raise ValueError('Wrong ESP chip image')
  full[offset:offset+len(data)]=data;records[name]={'offset':offset,'bytes':len(data),'sha256':digest(data)}
 full[FS_OFFSET:FS_OFFSET+FS_SIZE]=raw
 if full[0x9000:0xf000]!=b'\xff'*0x6000 or read_image(full[FS_OFFSET:],FS_SIZE)!=expected:raise ValueError('Merged flash readback failed')
 (out/NAME).write_bytes(full)
 component_versions={key:json.loads(expected[path])['version'] for key,path in [
  ('panel_driver','display/manifest.json'),('power_rail','rail/manifest.json'),('battery_driver','battery/manifest.json')]}
 receipt={'schema':1,'product':'Waveshare first-boot test','version':'0.1.8','shared_home':'0.15.0','image':NAME,'bytes':len(full),'sha256':digest(full),'write_address':0,'native_regions':records,'bootfs':{'offset':FS_OFFSET,'bytes':FS_SIZE,'sha256':digest(raw),'tool_sha256':TOOL_SHA},'source_pins':PINS,'device_commit':subprocess.check_output(['git','-C',str(device),'rev-parse','HEAD'],text=True).strip(),'store_files':{n:{'bytes':len(v),'sha256':digest(v)} for n,v in sorted(expected.items())},'validation':{'real_runtime_admission':True,'native_export_and_elf_checks':True,'sanitizers':True,'independent_and_implementation_readback':True,'negative_cases':list(refusals)},'shared_home_staging':staging,**component_versions,'panel_boot_probe':'vendor paired rows; ALLPON-NORON red green blue startup probes; PMIC read-only','physical_boot_verified':False,'automatic_sleep':False,'network_required':False,'sd_required':False,'erases_lower_8mib_including_nvs':True,'paired_update':False}
 json_write(out/'build.json',receipt)
 (out/'SHA256SUMS.txt').write_text(receipt['sha256']+'  '+NAME+'\n')
 print('FLASH IMAGE READY:',NAME,len(full),'bytes',receipt['sha256'],flush=True)
if __name__=='__main__':main()
