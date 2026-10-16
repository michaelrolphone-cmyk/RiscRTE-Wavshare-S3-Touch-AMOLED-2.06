#!/usr/bin/env python3
"""Repeat source-pinned lifecycle and native-raster qualification without device I/O."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import subprocess
import sys
from package_launch_brightness import PINS, require, sha, encoded

SDK = {
 'RiscRuntimeV1.h': ('runtime','sdk/app/RiscRuntimeV1.h','80198965ebe3dda4d9cadbb5a6d64a44016041e8c2f610a6f636d915c6851831'),
 'RiscRealtimeV1.h': ('runtime','sdk/app/RiscRealtimeV1.h','639781f728841cda6d40c3033877436b9e5d59519a4b15e11a9bc99b2365395d'),
 'RiscAppDataV1.h': ('runtime','sdk/app/RiscAppDataV1.h','9eb18840ea691f88e85cca6ede3de4833467745ec29225a51a58cb84c0aac84e'),
 'AlarmServiceV1.h': ('utilities','lib/Alarm/include/AlarmServiceV1.h','c70c087550306c123255e1ace41aeb504809e16b0193e382ec8dfbd7cb5531f5'),
 'AlarmServiceV2.h': ('utilities','lib/Alarm/include/AlarmServiceV2.h','d7e750a8093e1b5e698483254edc38533b7242a3446d0bca5866c9dfd6ad07a1'),
}
ROLES = {'system':'system_revision','runtime':'runtime_revision','utilities':'utilities_revision','baseline_system':'baseline_system_revision','springboard_system':'springboard_revision','bridges':'bridge_revision'}

def snapshot(paths):
    rows = {}
    for name,path in paths.items():
        def git(*args):
            return subprocess.check_output(['git','-C',str(path),*args],text=True).strip()
        require(git('rev-parse','HEAD') == PINS[ROLES[name]], 'Source revision differs: '+name)
        require(not git('diff','HEAD','--name-only'), 'Tracked source is dirty: '+name)
        rows[name] = {'revision':git('rev-parse','HEAD'),'tree':git('rev-parse','HEAD^{tree}')}
    return rows

def verify_result(label, output):
    if label == 'springboard':
        data=json.loads((output/'results.json').read_bytes())
        require(len(data)==40 and all('PASS' in row['result'] for row in data), 'Springboard matrix incomplete')
        require(sum('application-' in row['case'] for row in data)==8, 'Real controller matrix incomplete')
        return {'cases':40,'real_controller_cases':8,'invocations_per_controller_case':3}
    if label == 'rf-raster':
        data=json.loads((output/'evidence.json').read_bytes())['runs']
        require(len(data)==8 and all('PASS' in row['result'] and 'comparisons=79 ' in row['result'] for row in data), 'RF raster matrix incomplete')
        require({(tuple(row['dimensions']),row['sanitized']) for row in data}=={((w,h),s) for w,h in ((160,160),(240,240),(410,502),(640,240)) for s in (False,True)}, 'RF raster profiles differ')
        return {'cases':8,'matching_frame_comparisons':632}
    expected={'custody':192,'custody-baseline':8,'brightness':126,'brightness-baseline':8}[label]
    data=json.loads((output/'receipt.json').read_bytes())['results']
    require(len(data)==expected and all(row['exit']==0 for row in data), 'Lifecycle matrix incomplete: '+label)
    require({row['mode'] for row in data}=={'normal','sanitized'}, 'Sanitizer coverage missing: '+label)
    return {'cases':expected}

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in (*ROLES,'output'):
        parser.add_argument('--'+name.replace('_','-'),type=Path,required=True)
    args=parser.parse_args();require(__debug__,'Do not use Python -O')
    paths={name:getattr(args,name).resolve() for name in ROLES}
    sources=snapshot(paths);out=args.output.resolve()
    require(not out.exists() or not any(out.iterdir()),'Output must be empty')
    out.mkdir(parents=True,exist_ok=True);sdk=out/'sdk';sdk.mkdir()
    for name,(role,relative,digest) in SDK.items():
        content=(paths[role]/relative).read_bytes()
        require(sha(content)==digest,'SDK digest differs: '+name)
        (sdk/name).write_bytes(content)
    system=paths['system'];py=sys.executable
    common=['--sdk-include',sdk,'--app-data-sdk',sdk,'--utilities-root',paths['utilities']]
    custody=[py,system/'scripts/test_shared_data_custody.py',*common]
    brightness=[py,system/'scripts/test_shared_initial_brightness.py',*common]
    commands={
      'custody':[*custody,'--callback-audit'],
      'custody-baseline':[*custody,'--source-root',paths['baseline_system'],'--test-source',system/'test/native_apps/shared_data_custody_test.c','--baseline'],
      'brightness':brightness,
      'brightness-baseline':[*brightness,'--source-root',paths['baseline_system'],'--baseline'],
      'springboard':[py,system/'scripts/test_springboard_launch_brightness.py','--springboard-root',paths['springboard_system'],'--bridges',paths['bridges'],'--sanitize'],
      'rf-raster':[py,system/'scripts/test_rf_native_raster.py'],
    }
    def qualify(item):
        label,command=item;destination=out/label
        command=[str(v) for v in [*command,'--output',destination]]
        log=out/(label+'.log')
        with log.open('w') as stream:
            result=subprocess.run(command,stdout=stream,stderr=subprocess.STDOUT,env={**os.environ,'ASAN_OPTIONS':'detect_leaks=0','UBSAN_OPTIONS':'halt_on_error=1','PYTHONDONTWRITEBYTECODE':'1'})
        require(result.returncode==0,'Qualification failed: '+label+'; see '+str(log))
        summary=verify_result(label,destination)
        print(label+': PASS',flush=True)
        return {'label':label,**summary,'command':command,'log_sha256':sha(log.read_bytes())}
    with ThreadPoolExecutor(max_workers=3) as pool:
        results=list(pool.map(qualify,commands.items()))
    require(sources==snapshot(paths),'Sources changed during qualification')
    receipt={'passed':True,'sources':sources,'cases':results,'normal_and_sanitized':True,'hardware_tested':False,'device_accessed':False,'leak_detection':False,'sdk_sha256':{name:row[2] for name,row in SDK.items()}}
    (out/'qualification.json').write_bytes(encoded(receipt))
    print(json.dumps(receipt,indent=2))

if __name__=='__main__':
    main()
