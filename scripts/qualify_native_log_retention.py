"""Bounded production-adapter host checks; no device or SDK IRQ execution."""
import json,os,re,subprocess
from pathlib import Path
from package_serial_logging import pins,require,sha,encoded
CASES=('long-line','full-tx-ingress','partial-priority','disconnected-burst','reconnect-partial','queue-wrap','foreign-owner','recovery-retention','overflow')
def validate(q,p):
 require(q['runtime_revision']==p['runtime_revision'] and q['hardware_tested'] is False and q['actual_sdk_irq'] is False,'Log source/scope differs')
 require(len(q['profiles'])==4 and {(r['external'],r['sanitized']) for r in q['profiles']}=={(e,s) for e in (False,True) for s in (False,True)},'Log matrix missing')
 for r in q['profiles']:
  require(r['returncode']==0 and r['cases']==list(CASES) and re.fullmatch('[0-9a-f]{64}',r['log_sha256']),'Log result missing')
 require(q['input_sha256'] and all(re.fullmatch('[0-9a-f]{64}',v) for v in q['input_sha256'].values()),'Log inputs missing')
 return q
def qualify(runtime,output):
 p=pins(final=True);output.mkdir(parents=True)
 require(subprocess.check_output(['git','-C',str(runtime),'rev-parse','HEAD'],text=True).strip()==p['runtime_revision'],'Log source revision differs')
 require(not subprocess.check_output(['git','-C',str(runtime),'status','--porcelain','--untracked-files=no'],text=True),'Log source dirty')
 paths=('src/diagnostics/LiveLogQueue.h','src/ports/esp32s3/SleepDiagnostics.cpp','src/ports/esp32s3/NativePlatform.cpp','src/ports/esp32s3/NativeSerialFiles.cpp','src/runtime/serial/Files.cpp','test/native_log_retention_test.cpp','test/run_native_log_retention_test.sh')
 q=dict(runtime_revision=p['runtime_revision'],hardware_tested=False,actual_sdk_irq=False,input_sha256={n:sha((runtime/n).read_bytes()) for n in paths},profiles=[])
 for external in (False,True):
  for sanitized in (False,True):
   name=f'log-{int(external)}-{int(sanitized)}.txt';cmd=['bash',str(runtime/'test/run_native_log_retention_test.sh')]
   env={**os.environ,'EXTERNAL':str(int(external)),'SANITIZE':str(int(sanitized)),'ASAN_OPTIONS':'detect_leaks=0:abort_on_error=1','UBSAN_OPTIONS':'halt_on_error=1'}
   result=subprocess.run(cmd,env=env,capture_output=True);raw=result.stdout+result.stderr;(output/name).write_bytes(raw)
   require(result.returncode==0 and b'AddressSanitizer' not in raw and b'runtime error:' not in raw,'Log regression failed: '+name+'\n'+raw.decode(errors='replace'))
   require(all(('PASS '+c).encode() in raw for c in CASES),'Log case output missing')
   q['profiles'].append(dict(external=external,sanitized=sanitized,returncode=0,cases=list(CASES),command=cmd,log_file=name,log_sha256=sha(raw)))
 require(q['input_sha256']=={n:sha((runtime/n).read_bytes()) for n in paths},'Log inputs changed')
 validate(q,p);(output/'qualification.json').write_bytes(encoded(q));return q
def validate_archive(z,q):
 prefix='build-evidence/log-retention/'
 require(json.loads(z.read(prefix+'qualification.json'))==q,'Archived log qualification differs')
 for r in q['profiles']:require(sha(z.read(prefix+r['log_file']))==r['log_sha256'],'Archived log output differs')
