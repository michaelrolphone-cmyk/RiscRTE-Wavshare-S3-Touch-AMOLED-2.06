#!/usr/bin/env python3
"""Replay the paired candidate with pinned public inputs, never publish it."""
import argparse,hashlib,importlib.util,json,shutil,subprocess,sys,urllib.request,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def main():
 p=argparse.ArgumentParser()
 for k in ('runtime','helper','work'):p.add_argument('--'+k,type=Path,required=True)
 a=p.parse_args();a.work.mkdir(parents=True,exist_ok=True);a.work=a.work.resolve();runtime=a.runtime.resolve();helper=a.helper.resolve()
 public=a.work/'public';public.mkdir(exist_ok=True)
 meta=json.loads((ROOT/'docs/catalog-payload/pair-0.1.55/github-release55.json').read_bytes())
 for x in meta['assets']:
  target=public/x['name'];data=urllib.request.urlopen(x['browser_download_url'],timeout=120).read()
  if len(data)!=x['size'] or 'sha256:'+hashlib.sha256(data).hexdigest()!=x['digest']:raise ValueError('Changed public input '+x['name'])
  target.write_bytes(data)
 companion=a.work/'companion.zip';data=urllib.request.urlopen('https://github.com/michaelrolphone-cmyk/RiscRTE-Wavshare-S3-Touch-AMOLED-2.06/releases/download/test-lora-media-0.1.17/Waveshare-LoRa-0.1.17-SD-card.zip',timeout=120).read()
 if hashlib.sha256(data).hexdigest()!='f251cc299d3dbee2f758c4342f7869dff8f5b364a4c805920c754c0aedc518fd':raise ValueError('Changed companion')
 companion.write_bytes(data);z=zipfile.ZipFile(companion)
 expected={'Apps/lora_messages/lora_messages.elf','Apps/lora_messages/manifest.json','suite-card.json'}
 if set(z.namelist())!=expected or len(z.namelist())!=3:raise ValueError('Changed companion inventory')
 z.extractall(a.work/'lora/Waveshare-LoRa-0.1.17-SD-card')
 (a.work/'runtime').symlink_to(runtime,target_is_directory=True)
 baseline=a.work/'baseline';baseline.mkdir();shutil.copyfile(public/'qualification.json',baseline/'qualification.json')
 spec=importlib.util.spec_from_file_location('spiffs',helper/'scripts/read_only_spiffs.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
 for n,b in m.read_image((public/'store.bin').read_bytes(),0x550000).items():
  target=baseline/'store'/n;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(b)
 def run(script,*args):subprocess.run([sys.executable,str(ROOT/'scripts'/script),*map(str,args)],check=True)
 run('qualify_catalog_pair_lora_055.py','--base',a.work,'--work',a.work/'fresh-external','--helper-repo',helper,'--native-evidence',public/'Waveshare-0.1.55-WiFi-Footer-Evidence.zip')
 fresh=json.loads((a.work/'fresh-external/qualification.json').read_bytes());saved=json.loads((ROOT/'docs/catalog-payload/pair-0.1.55/external-elf/qualification.json').read_bytes())
 if fresh!=saved:raise ValueError('Fresh external proof differs')
 schema=a.work/'schema';schema.mkdir()
 revision='908355b0509907c05a6dc47a1ccc8e078d6e23b0';prefix='docs/catalog-payload/1.0.0/'
 paths=subprocess.check_output(['git','-C',str(runtime),'ls-tree','-r','--name-only',revision,'--',prefix],text=True).splitlines()
 if not paths:raise ValueError('Missing immutable schema object')
 for path in paths:
  target=schema/path.removeprefix(prefix);target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(subprocess.check_output(['git','-C',str(runtime),'show',revision+':'+path]))
 run('build_catalog_pair_055.py','--assets',public,'--companion',companion,'--runtime',runtime,'--schema',schema,'--output',a.work/'candidate')
 run('test_catalog_pair_055.py','--candidate',a.work/'candidate','--schema',schema)
 for mode in ('create','replace'):
  actual=(a.work/'candidate'/mode/'descriptor.json').read_bytes();wanted=(ROOT/'docs/catalog-payload/pair-0.1.55/candidates'/mode/'descriptor.json').read_bytes()
  if actual!=wanted:raise ValueError('Candidate digest replay differs: '+mode)
if __name__=='__main__':main()
