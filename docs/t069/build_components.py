from pathlib import Path
import json,shutil,subprocess,sys,hashlib
R=Path(__file__).resolve().parent
O=R/'t069-components';O.mkdir(exist_ok=True)
S=R/'system-t069';T=Path('/Users/micahelbyrns/Documents/Codex/2026-10-13/task/Runtime-wave-t051')
sdk=O/'sdk/include';sdk.mkdir(parents=True,exist_ok=True)
for folder in (R/'waterfall-startup-build/sdk/include',S/'lib/PortableApps/include',S/'sdk/app',T/'sdk/driver',T/'sdk/app'):
 for p in folder.glob('*.h'):shutil.copyfile(p,sdk/p.name)
for folder in (R/'utilities-spectrum-t069/lib/Alarm/include',R/'utilities-spectrum-t069/lib/Contexts/include'):
 for p in folder.glob('*.h'):
  if not (sdk/p.name).exists():shutil.copyfile(p,sdk/p.name)
shutil.copytree(S/'lib/PortableApps/time',sdk.parent/'time',dirs_exist_ok=True)
(O/'rf-presentation.h').write_text('#include "PaperPresentation.h"\n#define RF_PRESENTATION_H\n')
sys.path[:0]=[str(R/'utilities-spectrum-t069/scripts'),str(R/'wave-t069/scripts')]
from normalize_xtensa_relocations import normalize
from compact_cohort_elf import compact
for name,repo,recipe in [('waterfall','utilities-t069','waterfall-startup-build'),('audio_spectrum','utilities-spectrum-t069','spectrum-launch-build')]:
 raw=json.loads((R/recipe/'command.json').read_text());cmd=[]
 for arg in raw:
  arg=arg.replace(str(R/'system')+'/',str(S)+'/')
  for old in ('utilities-rf','utilities-current'):
   arg=arg.replace(str(R/old)+'/',str(R/repo)+'/')
  arg=arg.replace(str(R/'waterfall-startup-build/sdk/include'),str(sdk))
  arg=arg.replace(str(R/'waterfall-startup-build/rf-presentation.h'),str(O/'rf-presentation.h'))
  cmd.append(arg)
 cmd.insert(1,'-DPORTABLE_SPECTRUM_STAGE_TRACE');cmd.insert(1,'-I'+str(sdk))
 cmd[cmd.index('-o')+1]=str(O/(name+'.elf'))
 (O/(name+'-command.json')).write_text(json.dumps(cmd,indent=2)+'\n')
 with (O/(name+'-build.log')).open('w') as f:subprocess.run(cmd,check=True,stdout=f,stderr=subprocess.STDOUT)
 elf=O/(name+'.elf');n=normalize(elf);c=compact(elf,cmd[0]);receipt={'normalization':n,'compaction':c,'sha256':hashlib.sha256(elf.read_bytes()).hexdigest(),'bytes':elf.stat().st_size}
 (O/(name+'-build.json')).write_text(json.dumps(receipt,indent=2)+'\n');print(name,receipt['bytes'],receipt['sha256'],flush=True)
