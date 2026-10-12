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
NAME='Waveshare-0.1.0-Home-0.14.2-boot-test-full-0x0.bin'
PINS={
 'runtime':'5323d1e834bdcc8e5e9fb0e8f76c383e46626801',
 'shared':'1430ce9501c74c0e101720e665ea88da81c84849',
 'controllers':'851b8998e804c57b2c9f42d9f8fd0a69e79f2b41',
 'generic':'422e1e81a498fb6bdab9abf086325afc05a532dc',
 'system':'14762601b3fa7bbeeac5ed565a6825534bf74dca',
 'utilities':'fc0bdbbbc600ce891e60c44d091fce0586ade7d8'}

def digest(data):return hashlib.sha256(data).hexdigest()
def json_write(path,value):
 path.parent.mkdir(parents=True,exist_ok=True)
 path.write_text(json.dumps(value,indent=2)+'\n')
def files(root):return {p.relative_to(root).as_posix():p.read_bytes() for p in root.rglob('*') if p.is_file()}
def run(*command,**kw):return subprocess.run(list(map(str,command)),check=True,**kw)
def main():
 p=argparse.ArgumentParser(description=__doc__)
 for name in ('runtime','shared','controllers','generic','system','utilities','native','cc','mkspiffs','output'):
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
 run(sys.executable,S/'scripts/build.py','--system',dirs['system'],'--utilities',dirs['utilities'],'--cc',cc,'--output',components)
 validator=components/'validate-elf'
 def build(source,target,includes,symbol,extra=()):
  target.parent.mkdir(parents=True,exist_ok=True)
  version=target.with_suffix('.map');version.write_text('{ global: '+symbol+'; local: *; };\n')
  run(cc,'-std=c11','-Os','-fPIC','-mtext-section-literals','-mlongcalls','-fvisibility=hidden','-ffreestanding','-fno-builtin','-nostdlib','-nostartfiles','-shared','-Wl,--gc-sections','-Wl,--no-relax','-Wl,--hash-style=sysv','-ffunction-sections','-fdata-sections','-Wl,--version-script='+str(version),'-Wall','-Wextra','-Werror','-Wno-misleading-indentation',*['-I'+str(v) for v in includes],source,*extra,'-lgcc','-o',target)
  normalize(target);compact(target,str(cc),debug_path=components/'debug'/(target.parent.name+'-'+target.name))
  run(validator,target);version.unlink()
 boot={'board':'board.json','default_app':'default.elf','provider_activation':'demand-retained','drivers':[],'app_capabilities':[]}
 for name,instance,source in [('gpio',1,T/'drivers/twatch_gpio/driver.c'),('i2c',2,T/'drivers/twatch_i2c/i2c_main.c')]:
  build(source,store/name/'driver.elf',[S/'sdk/driver',T/'include'],'t5_driver_get')
  shutil.copy2(source.parent/'manifest.json',store/name/'manifest.json')
  boot['drivers'].append({'manifest':name+'/manifest.json','instance_id':instance})
 for name,folder,instance in [('battery','power_axp2101',4),('display','panel_co5300',5),('touch','touch_ft3168',6),('motion','motion_qmi8658',7),('rtc','rtc_pcf85063',8),('haptic','haptic_gpio',9)]:
  source=device/'drivers'/folder
  build(source/'driver.c',store/name/'driver.elf',[S/'sdk/driver',S/'include',device/'include'],'t5_driver_get')
  shutil.copy2(source/'manifest.json',store/name/'manifest.json')
  boot['drivers'].append({'manifest':name+'/manifest.json','instance_id':instance})
 build(G/'Drivers/legacy_power_key/driver.c',store/'powerkey/driver.elf',[G/'sdk/driver',S/'sdk/driver'],'t5_driver_get')
 shutil.copy2(G/'Drivers/legacy_power_key/manifest.json',store/'powerkey/manifest.json')
 boot['drivers'].append({'manifest':'powerkey/manifest.json'})
 board=json.loads((device/'hardware/board.json').read_text())
 board['devices']=[d for d in board['devices'] if d['instance_id'] in (1,2,4,5,6,7,8,9)]
 json_write(store/'board.json',board)
 def application(name,manifest,grants):
  manifest['file_name']=name+'.elf'
  manifest['requires']=[{'capability':c,'api':v} for c,v in dict.fromkeys((c,v) for c,v,i in grants)]
  json_write(store/(name+'.json'),manifest)
  boot['app_capabilities'].append({'manifest':name+'.json','grants':[{'capability':c,'api':v,'instance_id':i} for c,v,i in grants]})
 base=[('display.output',1,5),('board.battery',1,4),('rtc.clock',2,8),('input.touch.raw',1,6),('input.power-key',1,0),('runtime.realtime-control',1,0),('storage.key-value',1,1),('storage.key-value',1,5)]
 for role in ('default','clock'):
  manifest=json.loads((S/'apps/clock'/(role+'.json')).read_text())
  if manifest['version']!='0.14.2':raise ValueError('First-boot Home fixes are absent')
  shutil.copy2(components/(role+'.elf'),store/(role+'.elf'))
  application(role,manifest,base+([('runtime.provider-promotion',1,0)] if role=='default' else []))
 build(S/'apps/bringup/main.c',store/'springboard.elf',[S/'sdk/app',S/'sdk/driver',S/'include'],'app_main',[S/'apps/clock/viewport.c'])
 diagnostics={'type':'application','id':'watch-bringup','version':'0.1.0','architecture':'xtensa-esp32s3','entry':'app_main'}
 grants=[('display.output',1,5),('input.touch.raw',1,6),('board.battery',1,4),('rtc.clock',2,8),('motion.accel',1,7),('haptic.effect',1,9)]
 application('springboard',diagnostics,grants)
 # Existing Home's Wi-Fi shortcut routes to the honest unavailable/test screen,
 # not to a missing file or a pretend Wi-Fi provider.
 shutil.copy2(store/'springboard.elf',store/'wifi_settings.elf')
 application('wifi_settings',{**diagnostics,'id':'watch-radio-not-in-test'},grants)
 json_write(store/'boot.json',boot)
 expected=files(store)
 if len(expected)!=28 or sum(n.endswith('.elf') for n in expected)!=13:raise ValueError('Unexpected boot inventory')
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
         ('missing-provider',lambda:(damaged/'touch/manifest.json').unlink())]
  for name,mutate in cases:
   mutate();result=subprocess.run([str(checker),str(damaged)],text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
   if result.returncode!=4:raise ValueError(f'Invalid store was not cleanly refused: {name}: {result.stdout}')
   refusals[name]=result.stdout.strip()
   shutil.rmtree(damaged);shutil.copytree(unpacked,damaged)
 json_write(out/'negative-admission.json',refusals)
 # Validate the real compiled partition table, including its MD5 trailer.
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
 receipt={'schema':1,'product':'Waveshare first-boot test','version':'0.1.0','shared_home':'0.14.2','image':NAME,'bytes':len(full),'sha256':digest(full),'write_address':0,'native_regions':records,'bootfs':{'offset':FS_OFFSET,'bytes':FS_SIZE,'sha256':digest(raw),'tool_sha256':TOOL_SHA},'source_pins':PINS,'device_commit':subprocess.check_output(['git','-C',str(device),'rev-parse','HEAD'],text=True).strip(),'store_files':{n:{'bytes':len(v),'sha256':digest(v)} for n,v in sorted(expected.items())},'validation':{'real_runtime_admission':True,'native_export_and_elf_checks':True,'sanitizers':True,'independent_and_implementation_readback':True,'negative_cases':list(refusals)},'physical_boot_verified':False,'automatic_sleep':False,'network_required':False,'sd_required':False,'erases_lower_8mib_including_nvs':True,'paired_update':False}
 json_write(out/'build.json',receipt)
 (out/'SHA256SUMS.txt').write_text(receipt['sha256']+'  '+NAME+'\n')
 print('FLASH IMAGE READY:',NAME,len(full),'bytes',receipt['sha256'],flush=True)
if __name__=='__main__':main()
