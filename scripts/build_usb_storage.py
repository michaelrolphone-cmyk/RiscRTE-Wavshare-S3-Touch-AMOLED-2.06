#!/usr/bin/env python3
"""Build the async SDMMC volume with generic eight-sector USB export support."""
import argparse,hashlib,json,subprocess,sys,shlex
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
for n in ('sdk','support','tools','output'):p.add_argument('--'+n,type=Path,required=True)
p.add_argument('--cc',required=True);a=p.parse_args();r=Path(__file__).resolve().parents[1];out=a.output.resolve();out.mkdir(parents=True,exist_ok=True)
sys.path.insert(0,str(a.tools.resolve()));from normalize_xtensa_relocations import normalize
from compact_current_elf import compact
elf=out/'driver.elf';mapping=out/'exports.map';mapping.write_text('{ global: t5_driver_get; local: *; };\n')
flags=['-std=c11','-Os','-fPIC','-mtext-section-literals','-mlongcalls','-fvisibility=hidden','-ffreestanding','-fno-builtin','-nostdlib','-nostartfiles','-shared','-Wl,--no-relax','-Wl,--hash-style=sysv','-Wl,--gc-sections','-ffunction-sections','-fdata-sections','-Wl,--version-script='+str(mapping),'-Wall','-Wextra','-Werror','-Wno-unused-function','-Wno-misleading-indentation','-Wno-overflow','-DWAVE_SD_ASYNC=1',*['-I'+str(q.resolve()) for q in (a.sdk,a.support,r/'include')]]
sources=[r/'drivers/storage_sdmmc/driver.c',*[r/'lib/storage_fatfs/fatfs'/(n+'.c') for n in ('ff','ffunicode')]]
cmd=[a.cc,*flags,*map(str,sources),'-lgcc','-o',str(elf)];subprocess.run(cmd,check=True);normalize(elf);proof=compact(elf,a.cc,debug_path=out/'uncompacted.elf')
symbols=subprocess.check_output([a.cc.removesuffix('gcc')+'nm','-D',str(elf)],text=True);imports=sorted({line.split()[-1] for line in symbols.splitlines() if ' U ' in ' '+line})
assert set(imports)<=set('memchr memcmp memcpy memset strchr strcmp strlen strrchr'.split()),imports
manifest=r/'drivers/storage_sdmmc/manifest-async.json';(out/'manifest.json').write_bytes(manifest.read_bytes());sha=lambda b:hashlib.sha256(b).hexdigest();deps={}
for src in sources:
 d=subprocess.check_output([a.cc,'-MM',*flags,str(src)],text=True)
 for name in shlex.split(d.replace('\\\n',' ').split(':',1)[1]):
  f=Path(name).resolve();deps[str(f)]=sha(f.read_bytes())
for f in (manifest,Path(__file__)):deps[str(f.resolve())]=sha(f.read_bytes())
record=dict(version=json.loads(manifest.read_text())['version'],source_revision=subprocess.check_output(['git','-C',str(r),'rev-parse','HEAD'],text=True).strip(),source_dirty=bool(subprocess.check_output(['git','-C',str(r),'status','--porcelain'],text=True).strip()),sha256=sha(elf.read_bytes()),bytes=elf.stat().st_size,imports=imports,compaction=proof,command=cmd,source_sha256=deps,hardware_tested=False)
(out/'build.json').write_text(json.dumps(record,indent=2)+'\n');print(record['sha256'],record['bytes'])
