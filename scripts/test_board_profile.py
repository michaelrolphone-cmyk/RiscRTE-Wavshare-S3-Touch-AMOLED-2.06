#!/usr/bin/env python3
"""Check actual provider descriptors against the board's typed hardware map."""
import json
from pathlib import Path
R=Path(__file__).resolve().parents[1]
p=json.loads((R/'hardware/providers.json').read_text());b=json.loads((R/'hardware/board.json').read_text())
devices={d['instance_id']:d for d in b['devices']}
assert len(devices)==len(b['devices'])
seen=set()
for name,instance in p['physical'].items():
 m=json.loads((R/'drivers'/name/'manifest.json').read_text());d=devices[instance]
 assert any(h['compatible']==d['compatible'] and h['config_type']==d['config_type'] and h['config_version']==d['config_version'] and d['chip']['revision'] in h['revisions'] for h in m['hardware_compatibility']),name
 for cap in m['provides']:
  assert cap['capability'] not in seen;seen.add(cap['capability'])
assert len(p['physical'])==8
assert devices[5]['config']['width']==devices[6]['config']['width']==410
assert devices[5]['config']['height']==devices[6]['config']['height']==502
assert devices[12]['config']['pins']==[2,1,3,17]
assert devices[9]['config']['pins']==[18]
assert devices[10]['config']['mclk']==16 and devices[10]['config']['enable']==46
assert not set(p['absent_hardware_capabilities'])&seen
print('Eight provider manifests match typed board configuration and generic capabilities')
