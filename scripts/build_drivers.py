#!/usr/bin/env python3
"""Build board providers against the shared watch ABI and actual Runtime loader."""
import argparse,hashlib,json,os,subprocess,sys
from pathlib import Path
R=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser(description=__doc__)
for name in ('watch','system'):p.add_argument('--'+name,type=Path,required=True)
p.add_argument('--cc',required=True);p.add_argument('--output',type=Path,default=R/'dist/providers');a=p.parse_args()
w=a.watch.resolve();s=a.system.resolve();out=a.output.resolve();out.mkdir(parents=True,exist_ok=True)
sys.path.insert(0,str(w/'scripts'))
from normalize_xtensa_relocations import normalize
from compact_current_elf import compact
validator=out/'validate-elf'
subprocess.run([os.environ.get('CC','cc'),'-std=c11','-Wall','-Wextra','-Werror','-I'+str(s/'test/native_apps/stubs'),'-I'+str(s/'lib/elf_loader/include'),str(s/'lib/elf_loader/src/esp_elf_validate.c'),str(s/'test/native_apps/validate_test.c'),'-o',str(validator)],check=True)
records={}
for folder in sorted((R/'drivers').iterdir()):
 if not (folder/'driver.c').exists():continue
 target=out/folder.name;target.mkdir(exist_ok=True);elf=target/'driver.elf';mapping=target/'exports.map';mapping.write_text('{ global: t5_driver_get; local: *; };\n')
 cmd=[a.cc,'-std=c11','-Os','-fPIC','-mtext-section-literals','-mlongcalls','-fvisibility=hidden','-ffreestanding','-fno-builtin','-nostdlib','-nostartfiles','-shared','-Wl,--no-relax','-Wl,--hash-style=sysv','-Wl,--gc-sections','-ffunction-sections','-fdata-sections','-Wl,--version-script='+str(mapping),'-Wall','-Wextra','-Werror','-Wno-misleading-indentation',*['-I'+str(x) for x in (R/'include',w/'sdk/driver',w/'sdk/app',w/'include')],str(folder/'driver.c'),*([str(R/'lib/storage_fatfs/fatfs'/(name+'.c')) for name in ('ff','ffunicode')] if folder.name=='storage_sdmmc' else []),'-Wno-overflow','-lgcc','-o',str(elf)]
 subprocess.run(cmd,check=True);normalize(elf);proof=compact(elf,a.cc,debug_path=out/'debug'/(folder.name+'.elf'));subprocess.run([str(validator),str(elf)],check=True)
 symbols=subprocess.check_output([a.cc.removesuffix('gcc')+'nm','-D',str(elf)],text=True)
 imports={line.split()[-1] for line in symbols.splitlines() if ' U ' in ' '+line};exports={line.split()[-1] for line in symbols.splitlines() if len(line.split())>=3 and line.split()[-2] in ('T','D','B','R')}
 assert imports <= {'memcpy','memset','memcmp','memmove','strcmp','strncmp','strlen','strchr','snprintf','risc_runtime_get_api','malloc','free','calloc'},(folder,imports)
 assert exports=={'t5_driver_get'},(folder,exports)
 raw=elf.read_bytes();assert raw[:7]==b'\x7fELF\x01\x01\x01' and raw[16:20]==b'\x03\x00\x5e\x00'
 manifest=json.loads((folder/'manifest.json').read_text());(target/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
 records[folder.name]={'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw),'imports':sorted(imports),'compaction':proof,'physical_verification':False}
 print(folder.name+': target ABI and loader validation PASS',flush=True)
(out/'build.json').write_text(json.dumps({'schema':1,'providers':records},indent=2)+'\n')
