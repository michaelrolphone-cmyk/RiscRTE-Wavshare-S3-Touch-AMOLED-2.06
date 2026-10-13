#!/usr/bin/env python3
"""Build a local catalog-consumer checkpoint from an admitted storage candidate.

Does not assemble firmware. Standalone Contexts retains its prior, unqualified
compiled catalog until its source owner supplies a runtime consumer.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys

SYSTEM = '72f435fcee376ec62d17ece6180753385ea547d9'
HELPER = '362537417c4f37bbb240879d5ba756686511fec1'
BRIDGES = '6e82fdcaec0b73ed700d2104cfb4d94f011c19d4'

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p, v): p.write_text(json.dumps(v, indent=2)+'\n')
def main():
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('candidate','system','helper','bridges','utilities','service-utilities','shared','cc','output'):
        p.add_argument('--'+key,type=Path,required=True)
    a=p.parse_args()
    for k,v in vars(a).items():setattr(a,k,v.resolve())
    for path,pin in ((a.system,SYSTEM),(a.helper,HELPER),(a.bridges,BRIDGES),
                     (a.utilities,'fc0bdbbbc600ce891e60c44d091fce0586ade7d8'),
                     (a.service_utilities,'80efb298c9ca8d0f62f9a31840c9e51d380b40f6'),
                     (a.shared,'ec768c7fae6fdb484fef28c6ec87f129b0a7f585')):
        assert subprocess.check_output(['git','-C',str(path),'rev-parse','HEAD'],text=True).strip()==pin
        assert not subprocess.check_output(['git','-C',str(path),'diff','HEAD','--name-only'],text=True).strip()
    if a.output.exists():raise ValueError('Use a new output directory')
    previous=json.loads((a.candidate/'composition.json').read_text())
    a.output.mkdir(parents=True)
    raw=a.output/'unsealed-store';shutil.copytree(a.candidate/'store',raw)
    components=a.output/'components';components.mkdir()
    sys.path.insert(0,str(a.shared/'scripts'))
    from compact_current_elf import compact
    from normalize_xtensa_relocations import normalize
    reports={};cc=str(a.cc);nm=cc.removesuffix('gcc')+'nm'
    def compile(name,command,expected=None):
        mapping=components/(name+'.map');mapping.write_text('{ global: app_main; app_module_init; app_module_fini; local: *; };\n')
        elf=components/(name+'.elf')
        command=[str(x) for x in command]+([] if expected else ['-Wl,--version-script='+str(mapping),'-lgcc'])+['-o',str(elf)]
        assert not any(x.endswith(('/catalog.c','/empty_catalog.c','/watch-tools-catalog.c')) for x in command)
        subprocess.run(command,check=True)
        symbols=subprocess.check_output([nm,str(elf)],text=True)
        assert not any(x.split()[-1] in ('portable_catalog','portable_catalog_count') for x in symbols.splitlines() if x.split())
        before=sha(elf)
        linked_size=elf.stat().st_size
        if expected and (before != expected['expected_sha256'] or linked_size != expected['expected_size_bytes']):
            raise ValueError('Qualified shared artifact mismatch: '+name)
        dependencies=subprocess.check_output([*command[:-2], '-M'],text=True)
        paths=sorted({Path(x).resolve() for x in shlex.split(dependencies.replace('\\\n',' ')) if not x.endswith(':') and Path(x).is_file()})
        normalized_padding=normalize(elf)
        compaction=compact(elf,cc,debug_path=components/'debug'/(name+'.elf'))
        shutil.copy2(elf,raw/(name+'.elf'))
        reports[name]={'command':command,'linked_sha256':before,'linked_bytes':linked_size,'qualified_shared_recipe':bool(expected),'sha256':sha(elf),'bytes':elf.stat().st_size,'compiled_catalog_symbols':False,'normalization_padding_removed':normalized_padding,'compaction':compaction,
                       'sources':{x:sha(Path(x)) for x in command if x.endswith('.c') and Path(x).is_file()},
                       'transitive_inputs':{str(x):sha(x) for x in paths}}
    recipes=json.loads((Path(__file__).resolve().parents[1]/'profiles/shared-catalog-recipes.json').read_text())
    for role,recipe in recipes.items():
        values={'system':str(a.system),'bridge':str(a.bridges),'output':str(components)}
        command=[cc,*[arg.format(**values) for arg in recipe['arguments']]]
        compile(role,command,recipe)
    settings_manifest=json.loads((raw/'settings.json').read_text())
    settings_manifest['version']='1.3.24'
    write(raw/'settings.json',settings_manifest)
    for name in ('timecard','audio_spectrum'):
        original=previous['components'][name]['command'];old_system=next(x.split('/lib/PortableApps/',1)[0] for x in original if x.endswith('/lib/PortableApps/src/adapter.c'))
        command=[cc];skip=False
        for x in original[1:]:
            if skip:skip=False;continue
            if x=='-o':skip=True;continue
            if x=='-lgcc' or x.startswith('-Wl,--version-script=') or x.endswith('/empty_catalog.c'):continue
            command.append(x.replace(old_system,str(a.system)))
        compile(name,command)
    rows=re.findall(r'\.display_name="([^"]+)",\.file_name="([^"]+)",\.icon="([^"]+)"',(a.system/'test/native_apps/fixtures/watch_springboard_catalog_23.c').read_text())
    assert len(rows)==23
    presentation={filename:(name,icon) for name,filename,icon in rows}
    entries=[];boot=json.loads((raw/'boot.json').read_text())
    for policy in boot['app_capabilities']:
        manifest=json.loads((raw/policy['manifest']).read_text());row={'manifest':policy['manifest'],'id':manifest['id']}
        if manifest['file_name'] in presentation:
            row['display_name'],row['icon']=presentation[manifest['file_name']]
        if manifest['file_name'] in ('default.elf','springboard.elf'):row['launcher_visible']=False
        elif manifest['file_name']=='clock.elf':row['launcher_visible']=True
        entries.append(row)
    profile={'schema':1,'entries':entries,'consumers':[n+'.json' for n in reports]}
    write(a.output/'presentation.json',profile)
    subprocess.run([sys.executable,str(a.helper/'scripts/stage_app_catalog_metadata.py'),'--store',str(raw),'--profile',str(a.output/'presentation.json'),'--requirement-capacity','32','--grant-capacity','32','--output',str(a.output/'store')],check=True)
    for n in ('default.elf','clock.elf'):
        assert sha(a.output/'store'/n)==sha(a.candidate/'store'/n)
    write(a.output/'catalog-build.json',{'schema':1,'system':SYSTEM,'helper':HELPER,'bridges':BRIDGES,'components':reports,'flashable':False,'hardware_verified':False,'pending':['standalone Contexts source still uses compiled catalog','remaining Files/Waterfall/update composition','final device assembly and qualification'],'baseline_candidate':str(a.candidate)})
if __name__=='__main__':main()
