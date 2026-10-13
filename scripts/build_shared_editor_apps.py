#!/usr/bin/env python3
"""Rebuild the selected shared watch editor applications without device access."""
import argparse,json,subprocess
from pathlib import Path
from compact_cohort_elf import compact
from normalize_xtensa_relocations import normalize
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser(description=__doc__)
for name in ('system','spectrum','rf','bridges','runtime','output','compiler'):p.add_argument('--'+name,type=Path,required=True)
a=p.parse_args();values={k:str(v.resolve()) for k,v in vars(a).items()};values['inputs']=str(ROOT/'profiles/shared-editor-inputs')
pins=json.loads((ROOT/'profiles/shared-editor-sources.json').read_text())
for name in ('system','spectrum','rf','bridges','runtime'):
 actual=subprocess.check_output(['git','-C',values[name],'rev-parse','HEAD'],text=True).strip()
 if actual!=pins[name]:raise ValueError('Source pin mismatch: '+name)
out=a.output.resolve();out.mkdir(parents=True,exist_ok=True);records={}
for name,row in json.loads((ROOT/'profiles/shared-editor-recipes.json').read_text()).items():
 command=[token.format(**values) for token in row['command']]
 with (out/(name+'-build.log')).open('w') as log:subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,check=True)
 elf=out/(name+'.elf');normalized=normalize(elf);result=compact(elf,values['compiler'])
 records[name]={'command':command,'normalization':normalized,'compaction':result}
(out/'build.json').write_text(json.dumps(records,indent=2)+'\n')
