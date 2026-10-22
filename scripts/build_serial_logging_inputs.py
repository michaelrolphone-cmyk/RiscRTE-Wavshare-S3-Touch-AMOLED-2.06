#!/usr/bin/env python3
"""Build only the URL-bearing catalog provider for the .62 core feed."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import subprocess
from package_serial_logging import pins, require,sha,record,encoded

def build(runtime,watch,system,compiler,output,record_only=False):
    p=pins();require(not output.exists(),'Input output must be new');output.mkdir(parents=True)
    sdk=output/'sdk';sdk.mkdir();sources={}
    # Runtime owns its published SDK. Watch fills names not owned by Runtime.
    for root,folders in ((runtime,('driver','hardware','app')),(watch,('driver','app'))):
        for folder in folders:
            for source in sorted((root/'sdk'/folder).glob('*.h')):
                target=sdk/source.name
                if target.exists():
                    if root==runtime:require(target.read_bytes()==source.read_bytes(),'Conflicting Runtime SDK name')
                    continue
                target.write_bytes(source.read_bytes());sources[str(source)] = record(source.read_bytes())
    (output/'sdk-sources.json').write_bytes(encoded(sources))
    product=Path(__file__).resolve().parents[1]
    subprocess.run(['python3',str(system/'scripts/build_installed_apps.py'),'--runtime-repo',str(runtime),'--output-dir',str(output/'catalog'),'--internal-packages','--boot-profiles','--native-feed','--feed-url',p['feed_url'],'--feed-product',p['feed_product'],'--time-server',p['time_server']],env={**os.environ,'NATIVE_APP_CC':str(compiler)},check=True)
    spec=importlib.util.spec_from_file_location('exact_compaction',watch/'scripts/compact_current_elf.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    folder=output/'catalog';receipt=json.loads((folder/'build.json').read_bytes());proof=module.compact(folder/'driver.elf',str(compiler),debug_path=folder/'original.elf')
    receipt['original_elf_sha256']=receipt['elf_sha256'];receipt['elf_sha256']=proof['after_sha256'];receipt['compaction']=proof
    (folder/'build.json').write_bytes(encoded(receipt))
    for folder,name in ((output/'catalog','installed-apps'),):
        for member in ('driver.elf','manifest.json'):
            if not record_only:
                require(record((folder/member).read_bytes())==(p['store_replacements'] if name+'/'+member in p['store_replacements'] else p['preserved_inputs'])[name+'/'+member],'Provider output differs: '+name+'/'+member)
    return {'catalog':receipt,'sdk_sources':sources}

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('runtime','watch','system','compiler','output'):parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--record-only',action='store_true',help='Measure first target build before locking exact bytes; not release qualification')
    print(json.dumps(build(**vars(parser.parse_args())),sort_keys=True))
