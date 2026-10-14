#!/usr/bin/env python3
"""Replay the qualified T054 production profile against the updated shared source."""
import argparse,json,subprocess,sys
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--command',type=Path,required=True);p.add_argument('--shared',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
a.output.mkdir(parents=True,exist_ok=True)
c=json.loads(a.command.read_text());target=a.output.resolve()/'springboard.elf';c[c.index('-o')+1]=str(target)
(a.output/'command.json').write_text(json.dumps(c,indent=2)+'\n');subprocess.run(c,check=True)
sys.path.insert(0,str(a.shared.resolve()/'scripts'))
from normalize_xtensa_relocations import normalize
from compact_current_elf import compact
normalize(target);compact(target,c[0],debug_path=a.output/'debug/springboard.elf')
