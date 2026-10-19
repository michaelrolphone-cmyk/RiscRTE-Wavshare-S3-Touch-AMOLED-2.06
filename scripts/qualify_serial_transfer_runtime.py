"""Run source-bound dedicated transfer controls; host execution only."""
import hashlib,json,os,re,subprocess,sys
from pathlib import Path
CASES=set(('live-hello live-control-hello malformed-sid short-sid zero-sid wrong-sequence extra-token short-frame partial-hello unframed-hello parked-hello pending-pair unconfirmed-boot disconnect-before-park disconnect-after-return late-postqueued postqueued-direct parked-storage-busy idle-keepalive idle-expiry partial-timeout duplicate-hello fresh-sid failed-shutdown failed-close legacy-live disconnect-active fini-admission-deadline fini-deadline-disconnect duplicate-after-ready-loss').split())
def require(ok,text):
    if not ok:raise ValueError(text)
def sha(raw):return hashlib.sha256(raw).hexdigest()
def validate(proof,revision):
    require(proof['schema']==1 and proof['passed'] is True and proof['runtime_revision']==revision,'Transfer proof/source missing')
    require(proof['hardware_tested'] is False and proof['target_instructions_executed'] is False,'Transfer proof scope differs')
    require(proof['compiled_runtime_rows']>0,'Selected native transfer compilation missing')
    require(len(proof['runs'])==4 and {(r['suite'],r['sanitized']) for r in proof['runs']}=={(s,z) for s in ('mode','settings') for z in (False,True)},'Transfer matrix incomplete')
    for run in proof['runs']:
        receipt=run['receipt']
        require(run['returncode']==0 and re.fullmatch('[a-f0-9]{64}',run['log_sha256']),'Transfer execution failed')
        require(receipt['revision']==revision and receipt['baseline'] is False and receipt['sanitized']==run['sanitized'] and receipt['immutable_inputs_verified'] is True and receipt['runtime_sources'],'Transfer input custody differs')
        if run['suite']=='mode':
            require(receipt['expectations_met'] is True and receipt['contract_suite_passed'] is True and set(receipt['selected_cases'])==CASES and len(receipt['results'])==len(CASES),'Transfer cases missing')
            require(set(r['case'] for r in receipt['results'])==CASES and all(r['returncode']==0 and r['expectation_met'] for r in receipt['results']),'Transfer case failed')
        else:require(receipt['passed'] is True and receipt['returncode']==0,'Accepted Settings drain failed')
    return proof

def qualify(runtime,output):
    runtime=Path(runtime);output=Path(output);require(not output.exists(),'New transfer evidence directory required');output.mkdir(parents=True)
    revision=subprocess.check_output(['git','-C',str(runtime),'rev-parse','HEAD'],text=True).strip()
    require(not subprocess.check_output(['git','-C',str(runtime),'status','--porcelain','--untracked-files=no'],text=True),'Dirty Runtime source')
    rows=[]
    for sanitized in (False,True):
        for suite,runner in [('mode','run_native_serial_transfer_mode_test.py'),('settings','run_native_settings_transfer_mode_test.py')]:
            folder=output/(suite+('-sanitized' if sanitized else '-normal'));cmd=[sys.executable,str(runtime/'test'/runner),'--output',str(folder)]
            result=subprocess.run(cmd,env={**os.environ,'SANITIZE':str(int(sanitized)),'ASAN_OPTIONS':'detect_leaks=0:halt_on_error=1','UBSAN_OPTIONS':'halt_on_error=1'},stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
            log=result.stdout.encode();(output/(folder.name+'.log')).write_bytes(log);result.check_returncode()
            receipt=json.loads((folder/'receipt.json').read_bytes());rows.append(dict(suite=suite,sanitized=sanitized,command=cmd,returncode=result.returncode,log_sha256=sha(log),receipt=receipt))
    proof=dict(schema=1,passed=True,runtime_revision=revision,hardware_tested=False,target_instructions_executed=False,compiled_runtime_rows=0,runs=rows,limits='Production host control paths; synthetic generic provider/boot eligibility and modeled Settings worker/NVS boundaries. Full native compilation is checked independently; physical timing remains unqualified.')
    return proof

def validate_archive(archive,proof):
    for run in proof['runs']:
        label=run['suite']+('-sanitized' if run['sanitized'] else '-normal')
        require(sha(archive.read('build-evidence/transfer-mode/'+label+'.log'))==run['log_sha256'],'Transfer archived log differs')
        require(json.loads(archive.read('build-evidence/transfer-mode/'+label+'/receipt.json'))==run['receipt'],'Transfer archived receipt differs')
