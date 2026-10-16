#!/usr/bin/env python3
"""Stage the unqualified T051 Wi-Fi/SD store without producing a flash image."""
import argparse, hashlib, json
from pathlib import Path
p = argparse.ArgumentParser(description=__doc__)
for name in ('baseline', 'wifi-elf', 'sd-provider', 'output'):
    p.add_argument('--' + name, type=Path, required=True)
a = p.parse_args()
if a.output.exists():
    raise SystemExit('Use a fresh output directory')
store = {f.relative_to(a.baseline).as_posix(): f.read_bytes() for f in a.baseline.rglob('*') if f.is_file()}
before = dict(store)
def read(name): return json.loads(store[name])
def write(name, value): store[name] = (json.dumps(value, indent=2) + '\n').encode()
boot = read('boot.json')
assert 'installation' not in boot, 'Review existing installation authority before changing it'
assert any(d.get('instance_id') == 12 and d['manifest'] == 'sd-volume/manifest.json' for d in boot['drivers'])
# Only bind native replica custody to the deployed volume. Do not enable the
# separate installed-app SD settings framework or alter namespace 1 policy.
boot['installation'] = dict(volume_instance=12, grants=[])
row = next(r for r in boot['app_capabilities'] if r['manifest'] == 'wifi_settings.json')
extra = [('ui.text-input', 0), ('app.catalog', 0), ('storage.key-value.atomic', 6), ('storage.key-value.availability', 6)]
for cap, instance in extra:
    grant = dict(capability=cap, api=1, instance_id=instance)
    if grant not in row['grants']: row['grants'].append(grant)
write('boot.json', boot)
manifest = read('wifi_settings.json');manifest['version'] = '1.1.30'
for cap, _ in extra:
    requirement = dict(capability=cap, api=1)
    if requirement not in manifest['requires']: manifest['requires'].append(requirement)
write('wifi_settings.json', manifest)
store['wifi_settings.elf'] = a.wifi_elf.read_bytes()
for name in ('driver.elf', 'manifest.json'):
    store['sd-volume/' + name] = (a.sd_provider / name).read_bytes()
sd = read('sd-volume/manifest.json')
assert dict(capability='platform.storage-worker', api=1) in sd['requires']
changed = sorted(k for k in store if store[k] != before[k])
assert set(changed) <= {'boot.json','wifi_settings.json','wifi_settings.elf','sd-volume/driver.elf','sd-volume/manifest.json'}
for name, data in store.items():
    target = a.output / 'store' / name;target.parent.mkdir(parents=True, exist_ok=True);target.write_bytes(data)
report = dict(qualified=False, changed_files=changed, installation=boot['installation'],
    namespace_1_policy_changed=False, native_firmware_replacement_required=True,
    remaining=['actual native lifecycle and Wi-Fi persistence qualification', 'complete cohort admission and assembly'],
    inventory={n:hashlib.sha256(b).hexdigest() for n,b in store.items()})
(a.output / 'stage.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps({k:v for k,v in report.items() if k != 'inventory'}, indent=2))
