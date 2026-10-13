#!/usr/bin/env python3
"""Build a pinned offline SPIFFS packer with explicit lossless write batching."""
import argparse,hashlib,io,json,subprocess,tarfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
PIN='112d65368043f01dd86813cb84e41b1159a34f6b'
SPIFFS='f5e26c4e933189593a71c6b82cda381a7b21e41c'
def export(repo,pin,destination):
 raw=subprocess.check_output(['git','-C',str(repo),'archive',pin]);destination.mkdir(parents=True,exist_ok=True)
 with tarfile.open(fileobj=io.BytesIO(raw)) as archive:
  for item in archive.getmembers():
   if item.name.startswith('/') or '..' in Path(item.name).parts or item.issym() or item.islnk():raise ValueError('Unsafe archive member')
  archive.extractall(destination)
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',required=True,type=Path);p.add_argument('--output',required=True,type=Path);p.add_argument('--batch-bytes',type=int,choices=(8192,65536,1048576),default=8192);a=p.parse_args();a.source=a.source.resolve();a.output=a.output.resolve()
 if a.output.exists():raise ValueError('Choose a new output')
 assert subprocess.check_output(['git','-C',str(a.source),'rev-parse',PIN],text=True).strip()==PIN
 assert subprocess.check_output(['git','-C',str(a.source/'spiffs'),'rev-parse',SPIFFS],text=True).strip()==SPIFFS
 export(a.source,PIN,a.output);export(a.source/'spiffs',SPIFFS,a.output/'spiffs')
 patch=ROOT/'tools/mkspiffs-write-batching.patch'
 subprocess.run(['git','apply',str(patch)],cwd=a.output,check=True)
 source=a.output/'main.cpp';text=source.read_text();assert text.count('data_buffer[8192]')==1
 if a.batch_bytes!=8192:source.write_text(text.replace('data_buffer[8192]',f'data_buffer[{a.batch_bytes}]'))
 command=['make','-j','1','TARGET_OS=host','CC=cc','CXX=c++','CPPFLAGS=-DSPIFFS_OBJ_META_LEN=4','BUILD_CONFIG_NAME=-arduino-esp32',f'VERSION=0.2.3-batch{a.batch_bytes}','SPIFFS_VERSION=v0.3.7-5-gf5e26c4']
 subprocess.run(command,cwd=a.output,check=True)
 receipt={'source_commit':PIN,'spiffs_commit':SPIFFS,'patch_sha256':hashlib.sha256(patch.read_bytes()).hexdigest(),'command':command,'tool_sha256':hashlib.sha256((a.output/'mkspiffs').read_bytes()).hexdigest(),'compiler':subprocess.check_output(['c++','--version'],text=True).splitlines()[0],'scope':'Offline write batching only; on-disk format and native SPIFFS configuration unchanged'}
 receipt.update(write_batch_bytes=a.batch_bytes,patched_main_sha256=hashlib.sha256(source.read_bytes()).hexdigest())
 (a.output/'build-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
if __name__=='__main__':main()
