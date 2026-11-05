#!/usr/bin/env python3
"""Wave ExternalVolume native dependency; final Wi-Fi product admission is separate."""
import io
import re
import sys
import json
import shlex
import subprocess
import tempfile
from pathlib import Path
from elftools.elf.elffile import ELFFile
from package_alarm_sleep import make_archive

def require(ok, message):
    if not ok: raise ValueError(message)

from shared_home_capacity import expanded, linked_capacity

def profile_delta(root,runtime,old,cmake):
    import shared_home_capacity as retained
    require(old=='profiles/shared-home-capacity.cmake','Retained capacity profile required')
    retained.profile_delta(root,runtime,'profiles/serial-transfer-native.cmake',cmake)
    before=expanded(root,runtime,old,cmake)
    after=expanded(root,runtime,'profiles/shared-wifi-native.cmake',cmake)
    additions={'RISC_NATIVE_SETTINGS_LOCAL_ONLY=0','RISC_NATIVE_SETTINGS_LOCAL_FRESH=0'}
    old_defs=before['definitions'].split(';')
    new_defs=after['definitions'].split(';')
    require(not any(x.split('=',1)[0] in {a.split('=',1)[0] for a in additions} for x in old_defs),
            'Parent now selects a durability policy; explicit reconciliation required')
    require(all(new_defs.count(x)==1 for x in additions),'Explicit external policy missing/ambiguous')
    require(sorted(new_defs)==sorted(old_defs+list(additions)),'Unrelated profile definition changed')
    require({k:v for k,v in before.items() if k!='definitions'}==
            {k:v for k,v in after.items() if k!='definitions'},'Non-definition profile selection changed')
    return before,after

def checked_macros(text,header):
    found={}
    for line in text.splitlines():
        match=re.fullmatch(r'#define (RISC_[A-Z0-9_]+) (.*)',line)
        if match: found[match[1]]=match[2]
    wanted={'RISC_NATIVE_SETTINGS_LOCAL_ONLY':'0','RISC_NATIVE_SETTINGS_LOCAL_FRESH':'0',
        'RISC_NATIVE_SETTINGS_VOLUME_INSTANCE':'12','RISC_NATIVE_SETTINGS_NAMESPACE_MASK':'3',
        'RISC_NATIVE_SETTINGS_MAX_WRITERS':'32','RISC_RUNTIME_ATOMIC_BINDING_CAPACITY':'34',
        'RISC_NATIVE_SETTINGS_FRESH_INTERNAL_FALLBACK':'1','RISC_NATIVE_SETTINGS_PORT_SELECTED':'1'}
    for key in ('RISC_NATIVE_SETTINGS_LOGICAL_OWNER','RISC_NATIVE_SETTINGS_WRITERS'):
        matches=re.findall(r'^#define '+key+r' (.*)$',header,re.M)
        require(len(matches)==1,'Preserved settings definition missing: '+key)
        wanted[key]=matches[0]
    compact=lambda text: re.sub(r'\s+','',text)
    for key,value in wanted.items():
        require(key in found and compact(found[key])==compact(value),'Compiled settings policy differs: '+key)
    return {key:found[key] for key in wanted}

def preprocess_command(row):
    original=row.get('arguments') or shlex.split(row['command'])
    result=[];skip=False
    for arg in original:
        if skip: skip=False;continue
        if arg in ('-o','-MF','-MT','-MQ'): skip=True;continue
        if arg in ('-c','-MD','-MMD','-MP'): continue
        result.append(arg)
    require(not skip,'Truncated compilation arguments')
    return result+['-E','-dM']

def settings_evidence(args,sources,commands,p,base):
    header=sources['product']/'profiles/native-idf61-settings.h'
    actual=base.native.git(sources['product'],'rev-parse','HEAD:profiles/native-idf61-settings.h').decode().strip()
    require(actual==p['settings_header_git_blob'],'Existing settings authority changed')
    selected=[row for row in commands if Path(row['file']).resolve()==sources['runtime']/'src/ports/esp32s3/NativeSettingsBackend.cpp']
    require(len(selected)==1,'Expected one actual Backend compilation')
    command=preprocess_command(selected[0])
    output=subprocess.check_output(command,cwd=selected[0]['directory'],
        env=base.controlled.clean_environment(sources['sdk'],args.compiler),text=True)
    macros=checked_macros(output,header.read_text())
    folder=args.native_build/'native-build-evidence/external-settings-policy';folder.mkdir()
    (folder/'macros.txt').write_text(output)
    (folder/'command.json').write_bytes(base.encoded(command))
    report={'policy':'ExternalVolume','volume_instance':12,'namespace_mask':3,
        'settings_header_git_blob':actual,'preprocessed_macros':macros,
        'source':'actual NativeSettingsBackend.cpp compilation command',
        'macro_output_sha256':base.controlled.sha(output.encode())}
    (folder/'policy.json').write_bytes(base.encoded(report))
    return report

def baseline_policy(baseline,sources,base):
    from read_only_spiffs import read_image
    from prepare_preserving_update import layout,pair
    contract=base.package.baseline_contract()
    require(base.record(baseline)=={k:contract['factory'][k] for k in ('bytes','sha256')},
            'Exact released 0.1.64 baseline required')
    _,_,store=pair(baseline,0,layout(baseline))
    require(base.controlled.sha(store)==contract['store']['sha256'],'Baseline store differs')
    files=read_image(store,0x550000);base.package.check_baseline(files,contract)
    boot=json.loads(files['boot.json'])
    rows=[x for x in boot['drivers'] if x.get('instance_id')==12]
    require(len(rows)==1 and rows[0]['manifest']=='sd-volume/manifest.json','External volume12 owner differs')
    require(boot.get('installation',{}).get('volume_instance')==12,'Existing installation authority differs')
    manifest=json.loads(files['sd-volume/manifest.json'])
    require({'capability':'storage.volume','api':1} in manifest['provides'],'External storage interface missing')
    return {'released_store_sha256':contract['store']['sha256'],'volume_instance':12,
        'installation':boot['installation'],'store_files_verified':len(files),
        'store_modified':False,'appdata_nvs_sd_modified':False,
        'shared_wifi_companion_admission':False}

def qualify(args,sources,proof,base,cmake):
    controlled,native=base.controlled,base.native
    p=json.loads((base.ROOT/'docs/shared-wifi-native/source-pins.json').read_bytes())
    lock=json.loads(args.lock.read_bytes())
    closure=controlled.validate_build_proof(proof,sources,args.native_build,args.compiler,lock)
    before,after=profile_delta(base.ROOT,sources['runtime'],p['profile'],cmake)
    commands=json.loads((args.native_build/'compile_commands.json').read_bytes())
    rows=[]
    for row in commands:
        source=Path(row['file']).resolve()
        if not source.is_relative_to(sources['runtime']/'src'): continue
        arguments=row.get('arguments') or shlex.split(row['command'])
        for flag in after['definitions'].split(';'):
            if not flag: continue
            prefix='-D'+flag.split('=',1)[0]+'='
            require([x for x in arguments if x.startswith(prefix)]==['-D'+flag],
                    'Actual compile selection differs: '+flag)
        rows.append(row)
    require(rows,'No Runtime compilation')
    import sys
    sys.path[:0]=[str(sources['runtime']/'scripts'),str(sources['image_helper']/'scripts')]
    contract=json.loads(native.CONTRACT.read_bytes())
    # The verifier's default remains the frozen original profile. This explicit
    # caller supplies the separately evaluated and delta-checked derivative.
    blobs,native_proof=native.verify_native(lock,sources,args.native_build,args.compiler,
        contract,args.baseline.read_bytes(),profile_text=after['definitions'])
    policy=settings_evidence(args,sources,commands,p,base)
    baseline=baseline_policy(args.baseline.read_bytes(),sources,base)
    linked=linked_capacity(blobs['firmware_elf'])
    require(set(re.findall(rb'RISC_RUNTIME_VERSION:([^\x00]+)\x00',blobs['firmware_bin']))=={p['runtime_version'].encode()},'Runtime version marker differs')
    memory=args.native_build/'native-build-evidence/provider-capacity-layout'
    subprocess.run([sys.executable,str(sources['runtime']/'test/home_provider_capacity_layout.py'),'--build',str(args.native_build),'--runtime',str(sources['runtime']),'--output',str(memory)],check=True)
    measured=json.loads((memory/'memory.json').read_bytes())
    controlled.validate_build_proof(proof,sources,args.native_build,args.compiler,lock)
    native.verify_sources(lock,sources)
    report={'schema':1,'source_revision':lock['sources']['product']['revision'],
        'runtime_revision':p['runtime_revision'],'runtime_version':p['runtime_version'],'capacity_memory':measured,'settings_policy':policy,'released_baseline_policy':baseline,'profile_before':before,'profile_after':after,
        'compiled_runtime_rows':len(rows),'linked_capacity':linked,'native':native_proof,
        'build_closure_sha256':controlled.sha((args.native_build/'native-build-evidence/build-closure.json').read_bytes()),
        'scope':'Full native ExternalVolume firmware dependency; exact shared-Wi-Fi companion graph, persistence and heap admission remain separate.',
        'hardware_tested':False,'device_accessed':False,'product_composed':False}
    assets={name:blobs[key] for name,key in [('firmware.bin','firmware_bin'),('firmware.elf','firmware_elf'),
        ('bootloader.bin','bootloader'),('partitions.bin','partitions'),('firmware.map','firmware_map'),('compile_commands.json','compile_commands')]}
    assets['profile.cmake']=(base.ROOT/'profiles/shared-wifi-native.cmake').read_bytes()
    assets['settings.h']=(base.ROOT/'profiles/native-idf61-settings.h').read_bytes()
    report['artifacts']={name:base.record(raw) for name,raw in assets.items()}
    assets['qualification.json']=base.encoded(report)
    assets['source-lock.json']=args.lock.read_bytes()
    args.output.mkdir(parents=True)
    for name,raw in assets.items(): (args.output/name).write_bytes(raw)
    archive={}
    for role,root in sources.items():
        if role=='sdk': continue
        archive[role+'-source.tar']=native.git(root,'archive','--format=tar','HEAD')
    archive['qualification.json']=assets['qualification.json']
    assets['sources.zip']=make_archive(archive)
    (args.output/'sources.zip').write_bytes(assets['sources.zip'])
    (args.output/'SHA256SUMS').write_text(''.join(controlled.sha(raw)+'  '+name+'\n' for name,raw in sorted(assets.items())))
    print(json.dumps(report,sort_keys=True),flush=True)
