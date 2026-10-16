#!/usr/bin/env python3
"""Verify exact staged-region readbacks; performs no device I/O."""
import argparse,hashlib,json
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--plan',type=Path,required=True);p.add_argument('--readbacks',type=Path,required=True);p.add_argument('--selection',action='store_true',help='Verify selection-LAST only, after the three staged regions passed');a=p.parse_args()
plan=json.loads(a.plan.read_text());rows=plan['writes'][-1:] if a.selection else plan['writes'][:-1]
for row in rows:
 path=a.readbacks/row['file'];data=path.read_bytes()
 if len(data)!=row['bytes'] or hashlib.sha256(data).hexdigest()!=row['sha256']:raise SystemExit(row['file']+' readback mismatch; STOP')
 print(row['file']+' verified')
print('Selection readback verified; existing bootloader health/rollback applies.' if a.selection else 'All staged regions verified. The separate OTA selection sector is the final write.')
