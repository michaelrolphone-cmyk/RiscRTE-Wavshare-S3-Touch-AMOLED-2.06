#!/usr/bin/env python3
"""Exercise source pins, complete-cohort preservation and replay rejection gates."""
import copy
import io
import json
from pathlib import Path
import tempfile
import package_crash_sdr as m
from replay_crash_sdr_apps import emit_replay_logs, verify_receipt

passed = 0

def rejected(call):
    global passed
    try:
        call()
    except (ValueError, KeyError, FileNotFoundError):
        passed += 1
        return
    raise AssertionError('Invalid release input was accepted')

original_pins = copy.deepcopy(m.PINS)
original_apps = copy.deepcopy(m.APPS)

# Earlier retry diagnostics survive temporary replay-directory cleanup.
with tempfile.TemporaryDirectory(prefix='crash-replay-log-guards-') as td:
    root = Path(td)
    for name, text in [('waterfall.log', 'last attempt'), ('waterfall-link-attempts/attempt-01.log', 'first abort'), ('waterfall-link-attempts/attempt-02.log', ''), ('sources/ignored.log', 'source log'), ('work/ignored.log', 'work log')]:
        path = root / name; path.parent.mkdir(parents=True, exist_ok=True); path.write_text(text)
    output = io.StringIO(); emit_replay_logs(root, output); text = output.getvalue()
    assert all(value in text for value in ('waterfall.log', 'last attempt', 'waterfall-link-attempts/attempt-01.log', 'first abort', 'attempt-02.log', '(empty)'))
    assert 'source log' not in text and 'work log' not in text

m.PINS.update(finalized=True)
m.verify_final_pins()
for key, value in [('finalized', False), ('system_revision', None), ('runtime_revision', 'pending'),
                   ('version', '0.1.45'), ('baseline_version', '0.1.44'), ('publication_enabled', None),
                   ('performance_trace_capacity', 128), ('baseline_evidence_sha256', 'pending'),
                   ('baseline_product', '2'*40), ('baseline_runtime', '2'*40), ('native_changed', True),
                   ('changed_product_native_inputs', ['native/VendorDisplay.cpp']), ('app_count', 16),
                   ('changed_store_files', ['cohort.json']), ('changed_apps', ['waterfall', 'audio_spectrum'])]:
    old = m.PINS[key]; m.PINS[key] = value; rejected(m.verify_final_pins); m.PINS[key] = old
rejected(lambda: m.verify_baseline_bytes(b'wrong'))
rejected(lambda: m.verify_baseline_bytes(b'\xff' * 0x1000000))

# Every unrelated payload is preserved; manifests change only their version.
before = {f'preserved-{i}.elf': b'preserved'+bytes([i]) for i in range(43)}
before.update({'springboard.elf':b'native vector springboard', 'springboard.json':b'{"version":"1.7.17"}', 'default.elf':b'home', 'default.json':b'home policy', 'boot.json':b'wake grants', 'cohort.json':b'old cohort', 'directory/retained':b'retained'})
replacements = {}
for name, row in m.APPS.items():
    old = b'\x7fELF\x01\x01\x01'+b'\0'*9+b'\x03\x00\x5e\x00'+('old '+name).encode()
    before[name+'.elf'] = old
    before[name+'.json'] = json.dumps({'version':row['old_version'],'id':name,'requires':[{'cap':'unchanged'}]}).encode()
    data = b'\x7fELF\x01\x01\x01'+b'\0'*9+b'\x03\x00\x5e\x00'+name.encode()
    if name != 'waterfall':
        data = old
        row['proposed_version'] = row['old_version']
    replacements[name] = data
    row.update(deployed_sha256=m.sha(before[name+'.elf']), sha256=m.sha(data), bytes=len(data))
m.PINS.update(baseline_springboard_sha256=m.sha(before['springboard.elf']), baseline_springboard_manifest_sha256=m.sha(before['springboard.json']), baseline_home_sha256=m.sha(before['default.elf']))
store = m.replace_apps(before, replacements);store['cohort.json'] = b'new cohort'
assert len(m.verify_changed_store(before,store)) == 3
assert sum(n.endswith('.elf') and store[n]==before[n] for n in store)==61
for name in ('springboard.elf','springboard.json','default.elf','default.json','boot.json','directory/retained'):
    rejected(lambda name=name:m.verify_changed_store(before,dict(store,**{name:b'tampered'})))
rejected(lambda:m.verify_changed_store(before,dict(store,extra=b'extra')))
missing=dict(store);missing.pop('preserved-0.elf');rejected(lambda:m.verify_changed_store(before,missing))
for name in m.APPS:
    changed=dict(store);changed[name+'.json']=json.dumps({'version':m.APPS[name]['proposed_version']}).encode()
    rejected(lambda changed=changed:m.verify_changed_store(before,changed))
missing=dict(replacements);missing.pop(next(iter(m.APPS)));rejected(lambda:m.replace_apps(before,missing))
changed=dict(replacements);changed[next(iter(m.APPS))]=b'invalid';rejected(lambda:m.replace_apps(before,changed))

# Preserved apps must remain identical, even if a producer changes its claimed hash.
name='audio_spectrum'
original_row=copy.deepcopy(m.APPS[name]);changed=dict(replacements);changed[name]=replacements[name]+b'tampered'
m.APPS[name].update(sha256=m.sha(changed[name]),bytes=len(changed[name]))
rejected(lambda:m.replace_apps(before,changed));m.APPS[name].update(original_row)
old=m.APPS[name]['proposed_version'];m.APPS[name]['proposed_version']='99.0.0'
rejected(lambda:m.replace_apps(before,replacements));m.APPS[name]['proposed_version']=old
changed=dict(store);changed[name+'.json']=json.dumps(json.loads(store[name+'.json']),indent=2).encode()
rejected(lambda:m.verify_changed_store(before,changed))

# Complete replay receipts bind the actual output bytes, recipe, compiler and set.
with tempfile.TemporaryDirectory(prefix='crash-replay-guards-') as td:
    root=Path(td);compiler=root/'compiler';compiler.write_bytes(b'test compiler')
    source={'scripts/replay_shared_crash_apps.py':'driver','docs/shared-app-crashes/replay/inputs.json':'spec'}
    spec={'repositories':{'r0':{'repository':'owner/System','commit':'1'*40}}}
    receipt={'product':'wave','source_inputs_verified':True,'apps':{},'driver_sha256':'driver','spec_sha256':{'inputs.json':'spec'},'compiler':m.PINS['compiler_version'],'compiler_sha256':m.sha(compiler.read_bytes()),'repositories':spec['repositories']}
    for name,row in m.APPS.items():
        (root/(name+'.elf')).write_bytes(replacements[name]);receipt['apps'][name]={'sha256':row['sha256'],'bytes':row['bytes']}
    verify_receipt(receipt,root,spec,source,compiler)
    for key,value in [('product','twatch'),('source_inputs_verified',False),('driver_sha256','wrong'),('spec_sha256',{}),('compiler','wrong'),('compiler_sha256','wrong'),('repositories',{})]:
        changed=copy.deepcopy(receipt);changed[key]=value
        rejected(lambda changed=changed:verify_receipt(changed,root,spec,source,compiler))
    changed=copy.deepcopy(receipt);changed['apps'].pop(next(iter(m.APPS)));rejected(lambda:verify_receipt(changed,root,spec,source,compiler))
    name=next(iter(m.APPS));(root/(name+'.elf')).write_bytes(b'tampered');rejected(lambda:verify_receipt(receipt,root,spec,source,compiler))

m.PINS.clear();m.PINS.update(original_pins);m.APPS.clear();m.APPS.update(original_apps)
print(json.dumps(dict(passed=True,negative_cases=passed,complete_app_count=17,preserved_elf_count=61,changed_store_files=3)))
