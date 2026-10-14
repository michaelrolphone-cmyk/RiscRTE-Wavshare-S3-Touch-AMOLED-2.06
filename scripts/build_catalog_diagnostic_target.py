#!/usr/bin/env python3
"""Reproduce shipped .39, then build its diagnostic Springboard from source."""
import argparse,hashlib,io,json,subprocess,sys,tarfile,tempfile
from pathlib import Path
BASELINE='285f2e4417c19d7abad4a031d2130a339d410892'
EXPECTED='dad1a3ee9bbf7d88061e1a77b9ac81ba9fc7a584ed31fe423a56e57f0f3f4427'
BRIDGE='6e82fdcaec0b73ed700d2104cfb4d94f011c19d4'
ROOT=Path(__file__).resolve().parents[1]
def main():
 p=argparse.ArgumentParser(description=__doc__)
 for key in ('system','bridges','compiler','validator','output'):p.add_argument('--'+key,type=Path,required=True)
 a=p.parse_args()
 for k,v in vars(a).items():setattr(a,k,v.resolve())
 assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=a.bridges,text=True).strip()==BRIDGE
 assert not subprocess.check_output(['git','diff','HEAD','--name-only'],cwd=a.bridges,text=True).strip()
 sys.path.insert(0,str(a.bridges/'scripts'))
 from compact_current_elf import compact
 from normalize_xtensa_relocations import normalize
 original=json.loads((ROOT/'docs/catalog-display-custody/target-command.json').read_text())
 source=next(x[:-len('/Apps/springboard.c')] for x in original if x.endswith('/Apps/springboard.c'))
 bridge=next(x[:-len('/apps/clock/portable_navigation.c')] for x in original if x.endswith('/apps/clock/portable_navigation.c'))
 results=[];a.output.mkdir(parents=True,exist_ok=True)
 with tempfile.TemporaryDirectory(prefix='catalog-diagnostic-baseline-') as temporary:
  baseline=Path(temporary)
  archive=subprocess.check_output(['git','archive',BASELINE],cwd=a.system)
  with tarfile.open(fileobj=io.BytesIO(archive)) as tar:tar.extractall(baseline,filter='data')
  for name,system in (('baseline',baseline),('diagnostic',a.system)):
   out=a.output/name;out.mkdir(exist_ok=True);mapping=out/'exports.map'
   mapping.write_text('{global: app_main; app_module_init; app_module_fini;local:*;};\n')
   command=[x.replace(source,str(system)).replace(bridge,str(a.bridges)) for x in original]
   command[0]=str(a.compiler);command[command.index('-o')+1]=str(out/'springboard.elf')
   command=[('-Wl,--version-script='+str(mapping)) if x.startswith('-Wl,--version-script=') else x for x in command]
   subprocess.run(command,check=True);normalize(out/'springboard.elf');compact(out/'springboard.elf',str(a.compiler),debug_path=out/'springboard.debug.elf')
   subprocess.run([str(a.validator),str(out/'springboard.elf')],check=True)
   image=(out/'springboard.elf').read_bytes();digest=hashlib.sha256(image).hexdigest()
   symbols=subprocess.check_output([str(a.compiler).removesuffix('gcc')+'nm','-D',str(out/'springboard.elf')],text=True)
   imports=sorted({line.split()[-1] for line in symbols.splitlines() if ' U ' in ' '+line})
   exports=sorted({line.split()[-1] for line in symbols.splitlines() if len(line.split())>=3 and line.split()[-2] in ('T','D','B','R')})
   if name=='baseline':assert digest==EXPECTED
   else:assert imports==results[0]['imports'] and exports==results[0]['exports']
   normalized=[x.replace(str(system),'{system}').replace(str(a.bridges),'{bridges}').replace(str(out),'{output}').replace(str(a.compiler),'{compiler}') for x in command]
   results.append({'profile':name,'sha256':digest,'bytes':len(image),'imports':imports,'exports':exports,'command':normalized})
 report={'baseline_system':BASELINE,'bridge':BRIDGE,'results':results,'hardware_tested':False,'diagnostic_only':True}
 (a.output/'target-proof.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
if __name__=='__main__':main()
