#!/usr/bin/env python3
"""Run exact source lifetime, keep-set and post-return dual-namespace regressions."""
import json
import os
from pathlib import Path
import subprocess
import sys
from package_serial_lifetime import require, sha, encoded
CASES={'cold','absent-card','healthy','disconnect','failed-close','failed-write','failed-release','failed-prepare','post-return','post-failed-close','default-run'}
GUARDS=('admission','default-run','readiness','leaked-grant','leaked-consumer','undrained-old-session')
PROVIDER='e1b2fc8b801b33e3bd6ea30626a8dda9bf2237a6'

def qualify(runtime,provider,output):
    require(not output.exists(),'Lifetime evidence directory must be new');output.mkdir(parents=True)
    revision=subprocess.check_output(['git','-C',str(runtime),'rev-parse','HEAD'],text=True).strip()
    require(not subprocess.check_output(['git','-C',str(runtime),'status','--porcelain','--untracked-files=no'],text=True),'Runtime source is dirty')
    require(subprocess.check_output(['git','-C',str(provider),'rev-parse','HEAD'],text=True).strip()==PROVIDER,'Pinned provider source differs')
    rows=[]
    for sanitized in (False,True):
        label='sanitized' if sanitized else 'normal';root=output/label;root.mkdir()
        env={**os.environ,'SANITIZE':'1' if sanitized else '0','ASAN_OPTIONS':'detect_leaks=0:halt_on_error=1','UBSAN_OPTIONS':'halt_on_error=1','PYTHONDONTWRITEBYTECODE':'1'}
        commands=[['bash',str(runtime/'test/run_provider_keep_set_test.sh')],['bash',str(runtime/'test/run_native_serial_lifetime_guards_test.sh')],[sys.executable,str(runtime/'test/run_native_serial_waveshare_sd_test.py'),'--waveshare',str(provider),'--output',str(root/'wave')]]
        logs=[]
        for i,command in enumerate(commands):
            result=subprocess.run(command,cwd=runtime,env=env,capture_output=True,text=True)
            data=(result.stdout+result.stderr).encode();(root/f'command-{i}.log').write_bytes(data)
            require(result.returncode==0,'Lifetime regression failed: '+label+' '+str(i)+'\n'+data.decode(errors='replace')[-8000:])
            require('runtime error:' not in result.stderr and 'ERROR: AddressSanitizer' not in result.stderr,'Lifetime sanitizer failure')
            logs.append({'command':command,'returncode':result.returncode,'sha256':sha(data)})
        manifest=json.loads((root/'wave/source-manifest.json').read_bytes())
        require(set(manifest['cases'])==CASES and len(manifest['cases'])==len(CASES),'Lifetime matrix differs')
        require(manifest['immutable_inputs_verified'] is True and manifest['product_revision']==PROVIDER,'Lifetime source custody missing')
        require(manifest['sanitizers']==('address,undefined' if sanitized else 'none'),'Lifetime sanitizer scope differs')
        client=manifest['client'];require(client['requests']>0 and client['default_deadline_seconds']==5 and client['max_response_seconds']<5,'Actual post-return client deadline failed')
        rows.append({'build':label,'sanitized':sanitized,'passed':True,'logs':logs,'cases':manifest['cases'],'guard_cases':list(GUARDS),'provider_revision':PROVIDER,'source_manifest_sha256':sha((root/'wave/source-manifest.json').read_bytes()),'client':client})
        print('Native serial lifetime '+label+' PASS: exact graph, six guards, eleven SD cases and actual post-return client',flush=True)
    result={'schema':1,'passed':True,'runtime_commit':revision,'runtime_dirty':False,'provider_revision':PROVIDER,'cases':rows,'hardware_tested':False,'target_instructions_executed':False,'leak_sanitizer':False,'scope':'Production source host tests with RAM SD and independent pinned LittleFS; no physical failure-cause claim'}
    (output/'qualification.json').write_bytes(encoded(result));return result
