#!/usr/bin/env python3
"""Execute distinct production-source Runtime and Home session guard fixtures.

These fixtures model hardware/provider boundaries. They are not a combined target
execution and do not establish physical USB/SD timing or device acceptance.
"""
import json
import os
from pathlib import Path
import subprocess
import sys
from package_serial_transfer import pins, require, sha, record, encoded
SERIAL_CASES=('path','stale-ready','partial-frame','pending-request','pending-reply','partial-reply','read','write','disconnect-open','expiry','unavailable-media','settings-busy','null-hook','no-session','postcommit-arrival','return-shutdown','failed-close')
HOME_CASES=('swipe-active','swipe-pending','swipe-undrained','swipe-disconnect','swipe-no-session','swipe-late','wifi-active','wifi-no-session','contexts-export','contexts-export-no-session','contexts-workflow','contexts-workflow-message','contexts-export-late','contexts-workflow-late')
IDLE_CASES=('old-signal','lease-timeout','renewed-session','disconnect','no-session','manual-busy','blanking-arrival')

def validate(q,p):
    require(q['schema']==1 and q['passed'] is True and q['runtime_revision']==p['runtime_revision'] and q['watch_revision']==p['watch_revision'],'Session navigation source differs')
    require(q['hardware_tested'] is False and q['target_instructions_executed'] is False and q['combined_target_fixture'] is False,'Session navigation scope differs')
    require(len(q['runtime'])==4 and {(r['kind'],r['sanitized']) for r in q['runtime']}=={(k,s) for k in ('serial','settings') for s in (False,True)},'Runtime guard matrix incomplete')
    for row in q['runtime']:
        r=row['receipt']
        require(r['revision']==p['runtime_revision'] and r['baseline'] is False and r['sanitized']==row['sanitized'] and r['immutable_inputs_verified'] is True and r['runtime_sources'] and r['commands'],'Runtime guard custody missing')
        if row['kind']=='serial':
            require(len(r['results'])==len(SERIAL_CASES) and {x['case'] for x in r['results']}==set(SERIAL_CASES) and all(x['passed'] and x['returncode']==0 and not x['expected_regression_failure'] for x in r['results']),'Runtime serial guard results differ')
        else: require(r['passed'] is True and r['returncode']==0,'Settings launch guard failed')
    require(set(q['home'])=={'navigation','idle'},'Home guard scope missing')
    for key,cases in (('navigation',HOME_CASES),('idle',IDLE_CASES)):
        r=q['home'][key]['receipt']
        require(r['variant']=='fixed' and r['home_head']==p['watch_revision'] and r['runtime_head']==p['runtime_revision'] and r['hardware_tested'] is False and r['leak_detection'] is False,'Home guard source/scope differs')
        expected={(tuple(d),s,c) for d in ((240,240),(410,502)) for s in (False,True) for c in cases}
        require(len(r['runs'])==len(expected) and {(tuple(x['dimensions']),x['sanitized'],x['case']) for x in r['runs']}==expected and all(x['returncode']==0 and x['stdout'] and 'runtime error:' not in x['stderr'] and 'ERROR: AddressSanitizer' not in x['stderr'] for x in r['runs']),'Home guard matrix differs')
        require(len(r['compilations'])==4 and {(tuple(x['dimensions']),x['sanitized']) for x in r['compilations']}=={(d,s) for d in ((240,240),(410,502)) for s in (False,True)} and r['inputs'],'Home guard compilation custody missing')
    return q

def qualify(runtime,watch,system,utilities,output):
    p=pins(final=True);require(not output.exists(),'Session navigation output must be new');output.mkdir(parents=True)
    for root,rev in ((runtime,p['runtime_revision']),(watch,p['watch_revision'])):
        require(subprocess.check_output(['git','-C',str(root),'rev-parse','HEAD'],text=True).strip()==rev,'Guard source differs')
        require(not subprocess.check_output(['git','-C',str(root),'status','--porcelain','--untracked-files=no'],text=True),'Guard source dirty')
    q=dict(schema=1,passed=True,runtime_revision=p['runtime_revision'],watch_revision=p['watch_revision'],hardware_tested=False,target_instructions_executed=False,combined_target_fixture=False,runtime=[],home={},scope='Distinct production Runtime and Home host fixtures; modeled hardware/provider boundaries; no physical cause or device acceptance claim')
    def run(command,folder,env=None):
        result=subprocess.run(list(map(str,command)),capture_output=True,text=True,env=env)
        raw=(result.stdout+result.stderr).encode();(output/(folder.name+'.log')).write_bytes(raw)
        require(result.returncode==0 and 'runtime error:' not in result.stderr and 'ERROR: AddressSanitizer' not in result.stderr,'Session guard failed: '+folder.name+'\n'+raw.decode(errors='replace')[-6000:])
        receipt=(folder/'receipt.json').read_bytes()
        return dict(receipt=json.loads(receipt),receipt_file=folder.name+'/receipt.json',receipt_sha256=sha(receipt),log_file=folder.name+'.log',log_sha256=sha(raw))
    for sanitized in (False,True):
        env={**os.environ,'SANITIZE':'1' if sanitized else '0','ASAN_OPTIONS':'detect_leaks=0:abort_on_error=1','UBSAN_OPTIONS':'halt_on_error=1','PYTHONDONTWRITEBYTECODE':'1'}
        for kind in ('serial','settings'):
            folder=output/(kind+('-sanitized' if sanitized else '-normal'))
            row=run([sys.executable,runtime/f'test/run_native_{kind}_launch_test.py','--output',folder],folder,env)
            q['runtime'].append(dict(kind=kind,sanitized=sanitized,**row))
    for kind in ('navigation','idle'):
        folder=output/('home-'+kind)
        command=[sys.executable,watch/'scripts/test_serial_session_idle.py','--system',system,'--utilities',utilities,'--runtime',runtime,'--output',folder]
        if kind=='navigation':command+=['--navigation-only']
        q['home'][kind]=run(command,folder)
    validate(q,p);(output/'qualification.json').write_bytes(encoded(q));return q

def validate_archive(z,q):
    prefix='build-evidence/session-navigation/'
    require(json.loads(z.read(prefix+'qualification.json'))==q,'Archived session navigation proof differs')
    for row in q['runtime']+list(q['home'].values()):
        raw=z.read(prefix+row['receipt_file']);require(sha(raw)==row['receipt_sha256'] and json.loads(raw)==row['receipt'],'Archived guard receipt differs')
        require(sha(z.read(prefix+row['log_file']))==row['log_sha256'],'Archived guard log differs')
