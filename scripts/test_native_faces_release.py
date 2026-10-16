#!/usr/bin/env python3
"""Reject identity drift, malformed Home binaries and unrelated store changes."""
import copy, json
import package_native_faces as m
passed=0
def reject(fn):
 global passed
 try:fn()
 except (ValueError,KeyError,TypeError):passed+=1;return
 raise AssertionError('Invalid release input accepted')
m.verify_final_pins()
for key,value in [('version','0.1.46'),('baseline_version','0.1.45'),('finalized',False),('native_changed',True),('changed_store_files',['cohort.json','default.elf']),('preferences','nvs'),('crash_volume',6),('home_version','0.15.3'),('watch_revision','pending'),('home_sha256','bad'),('baseline_sha256','f'*64),('baseline_evidence_sha256','f'*64)]:
 old=m.PINS[key];m.PINS[key]=value;reject(m.verify_final_pins);m.PINS[key]=old
reject(lambda:m.verify_baseline_bytes(b'bad'));reject(lambda:m.verify_baseline_bytes(b'\xff'*0x1000000))
old=copy.deepcopy(m.PINS)
before={f'app-{i}.elf':b'keep'+bytes([i]) for i in range(60)}
before.update({'default.elf':b'old home','springboard.elf':b'old launcher','springboard.json':b'old manifest','default.json':json.dumps({'version':m.PINS['baseline_home_version'],'requires':[{'capability':'unchanged','api':1}],'custom':'preserved'}).encode(),'cohort.json':b'old cohort','boot.json':b'boot policy','unchanged.txt':b'text'})
home=b'\x7fELF\x01\x01\x01'+b'\0'*9+b'\x03\x00\x5e\x00native home'
m.PINS.update(baseline_home_sha256=m.sha(before['default.elf']),baseline_springboard_sha256=m.sha(before['springboard.elf']),home_sha256=m.sha(home),home_bytes=len(home))
store=m.replace_home(before,home);store['cohort.json']=b'new cohort';assert len(m.verify_changed_store(before,store))==3
assert sum(store[n]==before[n] for n in before if n.endswith('.elf'))==61
for name in before:
 if name not in m.PINS['changed_store_files']:
  reject(lambda name=name:m.verify_changed_store(before,dict(store,**{name:b'tampered'})))
reject(lambda:m.verify_changed_store(before,dict(store,extra=b'x')))
missing=dict(store);missing.pop('app-0.elf');reject(lambda:m.verify_changed_store(before,missing))
reject(lambda:m.replace_home(before,b'bad'))
reject(lambda:m.replace_home(dict(before,**{'default.elf':b'wrong'}),home))
reject(lambda:m.replace_home(dict(before,**{'default.json':b'{"version":"99.0.0"}'}),home))
reject(lambda:m.verify_changed_store(before,dict(store,**{'default.json':b'{"version":"0.16.0"}'})))
m.PINS.clear();m.PINS.update(old)
print(json.dumps({'passed':True,'negative_cases':passed,'preserved_elf_count':61,'changed_store_files':3}))
