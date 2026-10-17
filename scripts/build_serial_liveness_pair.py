#!/usr/bin/env python3
"""Produce the canonical .59 factory/SD pair after its real release ID exists.

The initial catalog content revision is an explicit proposed identity. The
caller MUST require the returned catalog payload-plan identity to match before
association. This command does not create catalog records or operate devices.
"""
import argparse
import copy
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import zipfile
from package_serial_liveness import pins,require,record,sha,encoded,ROOT,DOCS
from serial_liveness_release import verify_output

PAIR_MODES = ('create', 'replace', 'known-lora')
REPOSITORY = 'michaelrolphone-cmyk/RiscRTE-Wavshare-S3-Touch-AMOLED-2.06'


def release_identity(metadata, p, catalog_revision):
    revision = metadata['target_commitish']
    require(isinstance(revision, str) and re.fullmatch('[0-9a-f]{40}', revision), 'Immutable release source required')
    require(type(metadata['id']) is int and metadata['id'] > 0 and metadata['draft'] is False and
            metadata['prerelease'] is True and metadata['tag_name'] == p['release_tag'],
            'Actual public GitHub release identity required')
    require(type(catalog_revision) is int and catalog_revision == 1,
            'Only create-once initial catalog identity is selected')
    return revision


def verify_public_base(assets, metadata, tag):
    published = {row['name']: row for row in metadata['assets']}
    require(len(published) == len(metadata['assets']), 'Duplicate public asset names')
    prefix = 'https://github.com/' + REPOSITORY + '/releases/download/' + tag + '/'
    for path in assets.iterdir():
        require(path.is_file() and not path.is_symlink(), 'Invalid base asset path')
        data = path.read_bytes(); row = published.get(path.name)
        require(row is not None and row['state'] == 'uploaded' and
                row['size'] == len(data) and row['digest'] == 'sha256:' + sha(data) and
                row['browser_download_url'] == prefix + path.name,
                'Public base asset differs: ' + path.name)

def payload_entries(files, mode, historical):
    require(mode in PAIR_MODES, 'Unknown explicit per-file plan')
    require(len(historical)==3 and all(name in files and record(files[name])==row for name,row in historical.items()), 'Historical LoRa bytes differ')
    entries=[]
    for name,data in sorted(files.items()):
        operation='replace' if mode=='replace' or (mode=='known-lora' and name in historical) else 'create'
        previous=copy.deepcopy(historical[name]) if mode=='known-lora' and name in historical else None
        entries.append({'volume':'application-content','destination':'/'+name,'source':'payload/'+name,'operation':operation,'owner':'waveshare-boot-owned-external-apps','previous':previous,**record(data)})
    return entries



def git(root,revision,path):
    return subprocess.check_output(['git','-C',str(root),'show',revision+':'+path])


def schema_module(runtime,schema,p):
    for name in ('validate.py','manifest.schema.json','context.schema.json','descriptor.schema.json'):
        require((schema/name).read_bytes()==git(runtime,p['frozen_payload_schema'],'docs/catalog-payload/1.0.0/'+name),'Frozen payload schema differs: '+name)
    spec=importlib.util.spec_from_file_location('exact_payload_schema',schema/'validate.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def build(assets,release_record,runtime,schema,output,catalog_revision=1):
    p=pins(final=True);metadata=json.loads(release_record.read_bytes());revision=release_identity(metadata,p,catalog_revision)
    require(not output.exists(),'Pair output must be new')
    repo=REPOSITORY;catalog_id=repo.split('/',1)[1]+':'+p['release_tag']
    sums=(assets/'SHA256SUMS').read_bytes();verify_output(assets,sha(sums),revision)
    require(subprocess.check_output(['git','-C',str(ROOT),'rev-parse','HEAD'],text=True).strip()==revision,'Pair producer source differs')
    require(subprocess.check_output(['git','-C',str(runtime),'rev-parse','HEAD'],text=True).strip()==p['runtime_revision'],'Runtime source differs')
    verify_public_base(assets,metadata,p['release_tag'])
    v=schema_module(runtime,schema,p)
    q=json.loads((assets/'qualification.json').read_bytes());release=json.loads((assets/'release.json').read_bytes())
    factory_name='Waveshare-'+p['version']+'-SD-Apps-factory-erases-data-0x0.bin';factory=(assets/factory_name).read_bytes();store=(assets/'store.bin').read_bytes()
    require(len(factory)==16777216 and factory[0x2f0000:0x840000]==store,'Factory/store identity differs')
    require(factory[0x10000:0x10000+(assets/'firmware.bin').stat().st_size]==(assets/'firmware.bin').read_bytes(),'Factory/native identity differs')
    with zipfile.ZipFile(assets/'sd-apps.zip') as z:
        require(len(z.namelist())==len(set(z.namelist())),'Duplicate payload path');files={n:z.read(n) for n in z.namelist()}
    require({n:record(b) for n,b in files.items()}==q['preservation']['external_files_inventory'],'Qualified payload inventory differs')
    require(len(files)==45 and sum(map(len,files.values()))==3113484 and max(map(len,files.values()))==288112,'Full successor admission bounds differ')
    board=json.loads(git(ROOT,revision,'hardware/board.json'));require(board['board_id']=='waveshare-esp32-s3-touch-amoled-2.06' and board['revision']=='unspecified','Product identity differs')
    # These are release-specific write authorization bounds, never a claim of
    # provider capacity or available media space. They derive from all45 files.
    namespace={'namespace_id':'12','case_semantics':'ascii-insensitive','forbid_trailing_dot_space':True,'forbidden_characters':':\\*?"<>|','hierarchical':True,'max_component_bytes':127,'max_path_bytes':511,'max_file_bytes':max(map(len,files.values())),'operations':['stat','get','mkdir','create','replace'],'writable':True,'write_budget_bytes':sum(map(len,files.values()))}
    source_paths={'product':['hardware/board.json','drivers/storage_sdmmc/driver.c','lib/storage_fatfs/volume.c','lib/storage_fatfs/fatfs/ff.c','lib/storage_fatfs/fatfs/ffconf.h','include/RiscStorageVolumeV1.h'],
                  'runtime':['src/main.cpp','src/ports/esp32s3/NativeSerialStorage.cpp','src/runtime/serial/Files.cpp','src/runtime/serial/Files.h','sdk/app/RiscStorageFilesV1.h']}
    evidence_rows=[]
    for role,paths in source_paths.items():
        root=ROOT if role=='product' else runtime;rev=revision if role=='product' else p['runtime_revision']
        for path in paths:evidence_rows.append(dict(role=role,revision=rev,path=path,sha256=sha(git(root,rev,path))))
    base='https://github.com/'+repo+'/releases/download/'+p['release_tag']+'/'
    consumer={'id':'waveshare-boot-owned-external-apps','firmware_id':p['release_tag'],'evidence':{'url':base+'store.bin','sha256':sha(store)}}
    binding={'firmware_id':p['release_tag'],'volume':'application-content','namespace_id':'12','evidence':{'url':'https://github.com/michaelrolphone-cmyk/RiscRTE/blob/'+p['runtime_revision']+'/src/main.cpp','sha256':sha(git(runtime,p['runtime_revision'],'src/main.cpp'))}}
    evidence={'url':base+'release.json','sha256':sha((assets/'release.json').read_bytes())}
    install={'method_id':'esptool-full-0x0','kind':'factory','artifact_ids':['factory-image'],'settings_effect':'erased','erase_disclosure':'Full factory image at offset0 erases saved internal settings and device data. Back up first. Install the complete SD payload after flashing; external-volume survival is not assumed. Unrelated SD files and existing app-data are preserved by per-file operations.','volume_effects':[{'volume':'application-content','effect':'unknown','evidence':evidence}],'evidence':evidence}
    directories=set()
    for name in files:
        for parent in Path(name).parents:
            if str(parent)!='.':directories.add('/'+parent.as_posix())
    results={};output.mkdir(parents=True)
    historical=json.loads((DOCS/'baseline-0.1.58.json').read_bytes())['historical_external_companion']['files']
    for mode in PAIR_MODES:
        entries=payload_entries(files,mode,historical)
        operations=sorted({'stat','get','mkdir'}|{row['operation'] for row in entries})
        payload={'id':'waveshare-sd-apps-'+p['version'],'owner':'waveshare-boot-owned-external-apps','volumes':[{'id':'application-content','consumer':consumer,'requirements':{'case_semantics':namespace['case_semantics'],'hierarchical':True,'operations':operations,'path_encoding':'utf-8-exact'}}],'bindings':[binding],
            'directories':[{'volume':'application-content','path':name,'operation':'ensure-directory'} for name in sorted(directories)],
            'files':entries,
            'totals':{'file_count':len(files),'bytes':sum(map(len,files.values()))}}
        payload['inventory_sha256']=v.inventory_hash(payload)
        manifest={'schema_version':'1.0.0','container_format':'risc-catalog-payload-zip-store-v1','fixture':False,'description':'Waveshare0.1.59 exact full factory plus45-file SD application payload. Explicit '+mode+' per file; physical acceptance pending.',
            'catalog_release':{'id':catalog_id,'revision':catalog_revision,'repository':repo,'release_id':str(metadata['id']),'tag':p['release_tag'],'source_commit':revision},
            'product':{'id':board['board_id'],'hardware_profiles':['waveshare'],'hardware_revisions':[board['revision']],'storage_abi':'RiscStorageFilesV1','wire_protocol':'RTEF1','serial_contract_version':'1.0.0'},
            'firmware':{'id':p['release_tag'],'version':p['version'],'source_commit':revision,'artifacts':[{'id':'factory-image','source':'firmware/'+factory_name,**record(factory)}],'install':install},'payload':payload,
            'plan':{'purpose':'bootstrap','order':['firmware','payload','verify'],'pre_firmware_id':None,'policy':{'completion':'all-required-files-readable-by-target-consumer','on_partial_file':'retain-and-reconcile-selected-file','on_uncertain_result':'stop-inspect-no-automatic-retry','replacement':'explicit-selected-file-in-place-nonatomic','rollback':'none','unrelated_files':'preserve','verification':'commit-crc32-then-full-sha256-readback'}}}
        contents={'firmware/'+factory_name:factory,**{'payload/'+name:data for name,data in files.items()}}
        raw=v.pack(manifest,contents);require(raw==v.pack(manifest,dict(reversed(list(contents.items())))),'Nondeterministic canonical ZIP')
        context={'context_version':'1.0.0','fixture':False,'product_id':board['board_id'],'hardware_profile':'waveshare','hardware_revision':board['revision'],'installed_firmware_id':None,'supported_methods':['esptool-full-0x0'],
            'namespaces':[{'firmware_id':p['release_tag'],**namespace}],'limits':{'container_bytes':len(raw),'inventory_files':len(files)},
            'trusted_manifest_sha256':sha(v.canonical(manifest)),'trusted_container_sha256':sha(raw),'trusted_binding_sha256':[sha(v.canonical(binding))],'trusted_consumer_sha256':[sha(v.canonical(consumer))],'trusted_install_sha256':sha(v.canonical(install))}
        folder=output/mode;folder.mkdir();stem='Waveshare-'+p['version']+'-SD-Apps-'+mode
        (folder/(stem+'.zip')).write_bytes(raw);(folder/(stem+'.json')).write_bytes(v.canonical(manifest));(folder/'context.json').write_bytes(v.canonical(context))
        descriptor={'schema_version':'1.0.0','manifest':{'asset_name':stem+'.json',**record(v.canonical(manifest))},'container':{'asset_name':stem+'.zip',**record(raw)}}
        v.schema_check(descriptor,'descriptor.schema.json');(folder/'descriptor.json').write_bytes(v.canonical(descriptor))
        results[mode]=v.validate_container(folder/(stem+'.zip'),context)
    report={'schema':1,'results':results,'source_revision':revision,'runtime_revision':p['runtime_revision'],'schema_revision':p['frozen_payload_schema'],'github_release_id':metadata['id'],'expected_initial_catalog_revision':catalog_revision,'catalog_identity_requires_readback':True,'source_evidence':evidence_rows,'namespace':namespace,'publication_authorized':True,'hardware_tested':False,'live_capacity_verified':False,'plans':{'create':'All45 target paths must be absent.','replace':'All45 target paths must already exist; explicit replacement of these files only.','known-lora':'Exactly3 historical LoRa targets must match previous byte/hash guards; other42 target paths must be absent. Unrelated files and app-data are untouched.'},'automatic_operation_selection':False}
    (output/'qualification.json').write_bytes(encoded(report));return report

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('assets','release-record','runtime','schema','output'):parser.add_argument('--'+name,type=Path,required=True)
    print(json.dumps(build(**vars(parser.parse_args())),sort_keys=True))
