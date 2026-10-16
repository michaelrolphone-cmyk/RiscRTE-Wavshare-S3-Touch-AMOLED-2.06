#!/usr/bin/env python3
"""Prepare .43 from a fresh confirmed .41 readback; performs no device I/O."""
import argparse,hashlib,json,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--snapshot',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
metadata=json.loads((ROOT/'release.json').read_text())
for label in ('baseline','candidate'):
 path=ROOT/(label+'.bin')
 if hashlib.sha256(path.read_bytes()).hexdigest()!=metadata[label+'_sha256']:raise SystemExit(label+' integrity mismatch; STOP')
subprocess.run([sys.executable,str(ROOT/'prepare_preserving_update.py'),'--snapshot',str(a.snapshot.resolve()),'--baseline',str(ROOT/'baseline.bin'),'--candidate',str(ROOT/'candidate.bin'),'--baseline-sha256',metadata['baseline_sha256'],'--output',str(a.output.resolve())],check=True)
