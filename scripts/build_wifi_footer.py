#!/usr/bin/env python3
"""Reproduce retained Wi-Fi, then build the isolated footer correction."""
import argparse, hashlib, importlib.util, io, json, shutil, subprocess, tarfile
from pathlib import Path
from elftools.elf.elffile import ELFFile
from package_alarm_sleep import require, record, sha, encoded, clean_source

REPAIR='297c38619a867f6200cc2f605b6193e4394bdfa2'
OLD='021e92730e6263e6a590509d27d9a019ef93df1fc8a57486fe19dc196b7d031c'
FIXED='b8e45810e3529ed0300350fb9ae403059ff5c2bb1653bfb69d5ea25e05726cc3'
COMPILER='732bebd44b70a21687ffa3ac5da55edc9b555080ad21cfd74503b2288a143d3f'
VERSION='1.1.34'

def module(name,path):
    s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m

def build(repair,compiler,out,old_manifest,cache=None):
    repair,compiler,out=map(lambda p:Path(p).resolve(),(repair,compiler,out))
    clean_source(repair,REPAIR)
    require(sha(compiler.read_bytes())==COMPILER,'Exact retained compiler required')
    require(not out.exists(),'Fresh Wi-Fi output required');out.mkdir(parents=True)
    specdir=repair/'docs/shared-app-crashes/replay'
    spec=json.loads((specdir/'inputs.json').read_bytes());inputs={}
    for part in spec['input_parts']:inputs.update(json.loads((specdir/part).read_bytes()))
    row=json.loads((specdir/'wave.json').read_bytes())['wifi_settings']
    require(row['sha256']=='7bb9d98ace7cb783e6f85368c0dfd29360b96a635766c6f3f637b6901ae0d6c8' and row['bytes']==169460,'Released Wi-Fi recipe differs')
    paths={'cc':compiler,'work':out/'work'};sources={}
    for key in ('r0','r1','r2','r3'):
        pin=spec['repositories'][key];repo=out/'git'/key
        if cache and key in cache: repo=Path(cache[key]).resolve()
        else:
            repo.mkdir(parents=True);subprocess.run(['git','init','-q',repo],check=True)
            subprocess.run(['git','-C',repo,'fetch','--depth=1','https://github.com/'+pin['repository']+'.git',pin['commit']],check=True)
        data=subprocess.check_output(['git','-C',repo,'archive',pin['commit']]);target=out/'sources'/key;target.mkdir(parents=True)
        tarfile.open(fileobj=io.BytesIO(data)).extractall(target,filter='data');paths[key]=target
        sources[key]={**pin,'tree':subprocess.check_output(['git','-C',repo,'rev-parse',pin['commit']+'^{tree}'],text=True).strip()}
    def render(value):
        for key,path in sorted(paths.items(),key=lambda x:-len(x[0])):value=value.replace('@'+key+'@',str(path))
        require('@' not in value,'Unresolved recipe path');return value
    selected={n:r for n,r in inputs.items() if n.startswith(tuple('@'+k+'@/' for k in sources)) or n.startswith('@work@/target-basic/input-fixtures/') or n=='@work@/target-more/fixed/wifi_settings/exports.map'}
    for name,item in selected.items():
        if 'text' in item:
            require(sha(item['text'].encode())==item['template_sha256'],'Generated header template differs')
            path=Path(render(name));path.parent.mkdir(parents=True,exist_ok=True);path.write_text(render(item['text']))
        require('copy' not in item,'Unexpected external source copy')
    verified={}
    for name,item in selected.items():
        path=Path(render(name));require(sha(path.read_bytes())==item['sha256'],'Retained source differs: '+name);verified[name]=item['sha256']
    for name,item in spec['helper_files'].items():require(sha((specdir/name).read_bytes())==item['sha256'],'Replay helper differs')
    checked=module('wifi_checked',specdir/'checked_xtensa_link.py').compile_checked
    normalize=module('wifi_normalize',specdir/'normalize_xtensa_relocations.py').normalize
    compact=module('wifi_compact',specdir/'compact_current_elf.py').compact
    controller=paths['r0']/'Apps/wifi_settings_portable.inc'
    require(sha(controller.read_bytes())==OLD,'Retained controller differs')
    replacement=(repair/'Apps/wifi_settings_portable.inc').read_bytes();require(sha(replacement)==FIXED,'Qualified correction differs')
    results={}
    for label in ('baseline','fixed-a','fixed-b'):
        if label!='baseline':controller.write_bytes(replacement)
        command=list(row['command'])
        if label!='baseline':command=[('-DPORTABLE_WIFI_VERSION="'+VERSION+'"') if c.startswith('-DPORTABLE_WIFI_VERSION=') else c for c in command]
        command=[render(c) for c in command];target=out/label/'wifi_settings.elf';target.parent.mkdir();command[command.index('-o')+1]=str(target)
        attempts=checked(command,target,out/(label+'.log'));normalize(target);compaction=compact(target,str(compiler),debug_path=out/(label+'-uncompacted.elf'))
        elf=ELFFile(io.BytesIO(target.read_bytes()));symbols=elf.get_section_by_name('.dynsym')
        actual={'imports':sorted(s.name for s in symbols.iter_symbols() if s.name and s['st_shndx']=='SHN_UNDEF'),'exports':sorted(s.name for s in symbols.iter_symbols() if s.name and s['st_shndx']!='SHN_UNDEF')}
        require(actual==row['symbols'],'Wi-Fi import/export ABI changed')
        if label=='baseline':require(record(target.read_bytes())=={'bytes':row['bytes'],'sha256':row['sha256']},'Retained target reproduction differs')
        results[label]={'elf':record(target.read_bytes()),'symbols':actual,'command':command,'link_attempts':attempts,'compaction':compaction}
    a=(out/'fixed-a/wifi_settings.elf').read_bytes();b=(out/'fixed-b/wifi_settings.elf').read_bytes()
    require(a==b,'Independent Wi-Fi builds differ')
    manifest=json.loads(old_manifest);require(manifest['id']=='wifi_settings' and manifest['version']=='1.1.33','Released Wi-Fi manifest differs')
    manifest['version']=VERSION;manifest=encoded(manifest)
    proof={'schema':1,'repair_revision':REPAIR,'compiler_sha256':COMPILER,'sources':sources,'verified_source_files':verified,'controller_before_sha256':OLD,'controller_after_sha256':FIXED,'version':VERSION,'results':results,'independent_builds_identical':True,'manifest':record(manifest),'hardware_tested':False}
    (out/'wifi-build.json').write_bytes(encoded(proof));(out/'wifi_settings.elf').write_bytes(a);(out/'wifi_settings.json').write_bytes(manifest)
    clean_source(repair,REPAIR)
    return a,manifest,proof

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('repair','compiler','output','manifest'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--source-cache',type=Path)
    a=p.parse_args();elf,manifest,proof=build(a.repair,a.compiler,a.output,a.manifest.read_bytes(),json.loads(a.source_cache.read_text()) if a.source_cache else None)
    print(json.dumps({'elf':record(elf),'manifest':record(manifest),'version':VERSION}))
