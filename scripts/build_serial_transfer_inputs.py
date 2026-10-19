#!/usr/bin/env python3
"""Build selected transfer-mode Home and the version-bound catalog, without publication.

This is the .64 successor input producer. Historical .63 recipes remain exact.
A full native firmware/package qualification is a separate required step.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import zipfile

ROOT=Path(__file__).resolve().parents[1]
VERSION='0.1.64'
HOME_VERSION='0.20.4'
RUNTIME_VERSION='0.4.17'
FEED_URL='https://raw.githubusercontent.com/michaelrolphone-cmyk/RiscRTE-Wavshare-S3-Touch-AMOLED-2.06/provisioning-index/'+VERSION+'/native-packages-v1.json'
BASELINE_COMPANION_SHA='f800b5e3de0fb206646c7b00f28a2dc1c56357c677e79d5272fc4c5593bed0d8'
BASELINE_STORE_SHA='7c3b71dfcfd4a9cadd8a043393d4ffbaf9ac9d526ca263a63f85dcf519099119'

def require(ok,message):
    if not ok:raise ValueError(message)

def record(raw):return dict(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
def load_module(name,path):
    spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module

def home_command(watch,system,utilities,compiler,output):
    return [sys.executable,str(watch/'scripts/build.py'),'--system',str(system),'--utilities',str(utilities),'--cc',str(compiler),'--role','default','--automatic-provision','--serial-transfer-mode','--output',str(output)]

def require_home(path):
    receipt=json.loads((path/'build.json').read_bytes());manifest=json.loads((path/'default.json').read_bytes())
    require(receipt.get('serial_transfer_mode') is True and receipt.get('automatic_provision') is True,'Dedicated-transfer Home selection missing')
    flags=receipt['artifacts']['default']['defines']
    require(flags.count('-DWATCH_SERIAL_TRANSFER_MODE')==1,'Dedicated-transfer compile flag missing or ambiguous')
    require(manifest['version']==HOME_VERSION,'Dedicated-transfer Home version differs')
    require(record((path/'default.elf').read_bytes())=={k:receipt['artifacts']['default'][k] for k in ('bytes','sha256')},'Home ELF differs from compiler receipt')
    return receipt

def runtime_selection(commands,runtime):
    import shlex
    source=(runtime/'src').resolve();selected=[]
    for row in commands:
        path=Path(row['file']);path=(Path(row['directory'])/path).resolve() if not path.is_absolute() else path.resolve()
        if not path.is_relative_to(source):continue
        flags=row['arguments'] if 'arguments' in row else shlex.split(row.get('command',''))
        require([v for v in flags if v.startswith('-DRISC_NATIVE_SERIAL_TRANSFER_MODE=')]==['-DRISC_NATIVE_SERIAL_TRANSFER_MODE=1'],'Actual Runtime transfer-mode selection missing or ambiguous')
        selected.append(str(path))
    require(selected,'No actual Runtime compilation rows')
    return selected

def catalog_delta(before,after):
    old=b'/provisioning-index/0.1.63/';new=b'/provisioning-index/0.1.64/'
    require(before.count(old)==1 and before.replace(old,new)==after,'Catalog delta exceeds the exact version-bound URL change')

def build(runtime,watch,system,utilities,image_helper,compiler,baseline_store,baseline_companion,output):
    import configparser
    config=configparser.ConfigParser();config.read(runtime/'platformio.ini');require(config['riscrte']['version']==RUNTIME_VERSION,'Runtime version differs')
    require((ROOT/'profiles/serial-transfer-native.cmake').read_text().count('RISC_NATIVE_SERIAL_TRANSFER_MODE=1')==1,'Selected product Runtime profile missing transfer flag')
    require(not output.exists(),'Input output must be new');output.mkdir(parents=True)
    old_store=baseline_store.read_bytes();require(record(old_store)['sha256']==BASELINE_STORE_SHA,'Exact released .63 store required')
    sys.path.insert(0,str(image_helper/'scripts'));from read_only_spiffs import read_image
    before=read_image(old_store,0x550000)
    companion=baseline_companion.read_bytes();require(record(companion)['sha256']==BASELINE_COMPANION_SHA,'Exact released SD archive required')
    with zipfile.ZipFile(baseline_companion) as archive:
        require(len(archive.namelist())==len(set(archive.namelist())),'Duplicate SD paths')
        external={name:record(archive.read(name)) for name in sorted(archive.namelist())}
    require(len(external)==45 and sum(name.endswith('.elf') for name in external)==22,'External inventory differs')
    sdk=output/'sdk';sdk.mkdir();sdk_sources={}
    for owner,folders in ((runtime,('driver','hardware','app')),(watch,('driver','app'))):
        for folder in folders:
            for source in sorted((owner/'sdk'/folder).glob('*.h')):
                target=sdk/source.name
                if target.exists():
                    if owner==runtime:require(target.read_bytes()==source.read_bytes(),'Conflicting Runtime SDK name')
                    continue
                target.write_bytes(source.read_bytes());sdk_sources[str(source)]=record(source.read_bytes())
    (output/'sdk-sources.json').write_text(json.dumps(sdk_sources,indent=2)+'\n')
    commands=[]
    for suffix in ('a','b'):
        command=home_command(watch,system,utilities,compiler,output/('home-'+suffix));commands.append(command);subprocess.run(command,check=True)
        require_home(output/('home-'+suffix))
    verifier=load_module('selected_home_verifier',watch/'scripts/verify_shared_default.py')
    canonical=verifier.verify(output/'home-a',output/'home-b')
    command=[sys.executable,str(system/'scripts/build_installed_apps.py'),'--runtime-repo',str(runtime),'--output-dir',str(output/'catalog'),'--internal-packages','--boot-profiles','--native-feed','--feed-url',FEED_URL,'--feed-product','waveshare-s3-touch-amoled-206','--time-server','time.cloudflare.com']
    commands.append(command);subprocess.run(command,env={**os.environ,'NATIVE_APP_CC':str(compiler)},check=True)
    compactor=load_module('selected_catalog_compactor',watch/'scripts/compact_current_elf.py');folder=output/'catalog'
    catalog=json.loads((folder/'build.json').read_bytes());proof=compactor.compact(folder/'driver.elf',str(compiler),debug_path=folder/'original.elf')
    catalog['original_elf_sha256']=catalog['elf_sha256'];catalog['elf_sha256']=proof['after_sha256'];catalog['compaction']=proof
    (folder/'build.json').write_text(json.dumps(catalog,indent=2)+'\n')
    catalog_delta(before['installed-apps/driver.elf'],(folder/'driver.elf').read_bytes())
    require(before['installed-apps/manifest.json']==(folder/'manifest.json').read_bytes(),'Catalog manifest changed')
    replacements={name:record((output/path).read_bytes()) for name,path in [('default.elf','home-a/default.elf'),('default.json','home-a/default.json'),('installed-apps/driver.elf','catalog/driver.elf')]}
    receipt=dict(schema=1,version=VERSION,home_version=HOME_VERSION,runtime_version=RUNTIME_VERSION,commands=commands,canonical_home=canonical,replacements=replacements,baseline_store=record(old_store),baseline_companion=record(companion),external_files=external,retained_provider_files={name:record(raw) for name,raw in before.items() if name not in replacements and name!='cohort.json'},catalog_url_only=True,replacement_scope_home_and_url_catalog_only=True,device_accessed=False,published=False,limits='Fresh selected Home and catalog target builds only; Runtime actual compile selection must still be checked by runtime_selection against a complete fresh native build. No firmware link, package, physical timing or device acceptance.')
    (output/'input-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n');return receipt

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('runtime','watch','system','utilities','image-helper','compiler','baseline-store','baseline-companion','output'):parser.add_argument('--'+name,type=Path,required=True)
    print(json.dumps(build(**vars(parser.parse_args())),indent=2))
