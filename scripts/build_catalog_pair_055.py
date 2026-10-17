#!/usr/bin/env python3
"""Build unpublished Wave .55 canonical factory/payload candidates from exact inputs.

This producer does not publish or operate hardware. The admission policy is an
explicit, narrow product policy; it is not a claim of live media free space.
"""
import argparse, copy, hashlib, importlib.util, json, subprocess, sys, zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'docs/catalog-payload/pair-0.1.55'
PRODUCT='1606e7070753c87a9ba6160933331dbcc0d50162'
RUNTIME='f410c8592ecb37a520df3f29db8d88234dc7ddc9'
SCHEMA='908355b0509907c05a6dc47a1ccc8e078d6e23b0'
REPO='michaelrolphone-cmyk/RiscRTE-Wavshare-S3-Touch-AMOLED-2.06'
TAG='test-wifi-footer-0.1.55'
FACTORY='Waveshare-0.1.55-WiFi-Footer-factory-erases-data-0x0.bin'
def require(ok,msg):
    if not ok:raise ValueError(msg)
def sha(data):return hashlib.sha256(data).hexdigest()
def git(repo,rev,path):return subprocess.check_output(['git','-C',str(repo),'show',rev+':'+path])
def load(path):return json.loads(path.read_bytes())
def record(b):return {'bytes':len(b),'sha256':sha(b)}
def build(assets, companion, runtime, schema, output):
    policy=load(DATA/'product-admission.json')
    for row in policy['source_evidence']:
        require(sha(git(ROOT if row['role']=='product' else runtime,row['revision'],row['path']))==row['sha256'],'Source evidence differs: '+row['path'])
    for name in ('validate.py','manifest.schema.json','context.schema.json','descriptor.schema.json'):
        require((schema/name).read_bytes()==git(runtime,SCHEMA,'docs/catalog-payload/1.0.0/'+name),'Frozen schema differs: '+name)
    spec=importlib.util.spec_from_file_location('catalog_payload_v1',schema/'validate.py');v=importlib.util.module_from_spec(spec);spec.loader.exec_module(v)
    catalog=load(DATA/'catalog-release55.json');published=load(DATA/'github-release55.json')
    require(catalog['revision']==1 and catalog['data']['tag']==TAG and published['tag_name']==TAG and published['id']==415527412,'Frozen release identity differs')
    require(catalog['data']['source_commit']==PRODUCT and catalog['data']['flash']=={'profile':'waveshare','asset_name':FACTORY,'offset':0,'size':16777216},'Catalog flash admission differs')
    contents={}
    for asset in published['assets']:
        raw=(assets/asset['name']).read_bytes()
        require(len(raw)==asset['size'] and 'sha256:'+sha(raw)==asset['digest'],'Published asset differs: '+asset['name'])
    release=load(assets/'release.json');pins=load(assets/'source-pins.json')
    require(release['source_revision']==PRODUCT and pins['runtime_revision']==RUNTIME and pins['version']=='0.1.55','Producer lineage differs')
    factory=(assets/FACTORY).read_bytes();store=(assets/'store.bin').read_bytes()
    listed=next(a for a in catalog['data']['assets'] if a['name']==FACTORY)
    require(listed['size']==len(factory) and listed['digest']=='sha256:'+sha(factory),'Catalog factory digest differs')
    q=load(DATA/'external-elf/qualification.json');nativeq=load(assets/'qualification.json')
    require(q['runtime_commit']==RUNTIME and q['native_elf_sha256']==nativeq['admission']['native_elf_sha256'] and q['native_bin_sha256']==sha((assets/'firmware.bin').read_bytes()),'External ELF qualification lineage differs')
    require(q['published_cohort_closure']['store_digest']==nativeq['admission']['candidate_store_sha256'] and q['published_cohort_closure']['elf_count']==62,'Qualified internal cohort differs')
    require(q['all_required_capabilities_explicitly_granted'] and q['optional_lora_ungranted'] and {t['sanitized'] for t in q['tests']}=={True,False},'Missing capability/normal/sanitized proof')
    for t in q['tests']:
        require(t['production_structural_validation'] and t['production_application_admission'] and t['missing_import_rejections']==11 and t['production_removable_image_snapshots']==2,'Incomplete external ELF proof')
    require(len(factory)==16777216 and factory[0x2f0000:0x840000]==store,'Full factory/store pairing differs')
    require(factory[0x10000:0x10000+(assets/'firmware.bin').stat().st_size]==(assets/'firmware.bin').read_bytes(),'Full factory/native pairing differs')
    old=load(ROOT/'docs/catalog-payload/admission-0.1.52/baseline.json')['companion']
    raw=companion.read_bytes();require(record(raw)==old['assets']['Waveshare-LoRa-0.1.17-SD-card.zip'],'Companion archive differs')
    with zipfile.ZipFile(companion) as z:
        require(sorted(z.namelist())==sorted(old['files']),'Companion inventory differs')
        files={n:z.read(n) for n in z.namelist()}
        require({n:record(b) for n,b in files.items()}==old['files'],'Companion bytes differ')
    board=json.loads(git(ROOT,PRODUCT,'hardware/board.json'))
    require(board['board_id']==policy['product_id'] and board['revision']==policy['hardware_revision'],'Board identity differs')
    base='https://github.com/'+REPO+'/releases/download/'+TAG+'/'
    consumer={'id':'lora_messages','firmware_id':TAG,'evidence':{'url':base+'store.bin','sha256':sha(store)}}
    binding={'firmware_id':TAG,'volume':'application-content','namespace_id':'12','evidence':{'url':'https://github.com/michaelrolphone-cmyk/RiscRTE/blob/'+RUNTIME+'/src/main.cpp','sha256':sha(git(runtime,RUNTIME,'src/main.cpp'))}}
    evidence={'url':base+'release.json','sha256':sha((assets/'release.json').read_bytes())}
    install={'method_id':'esptool-full-0x0','kind':'factory','artifact_ids':['factory-image'],'settings_effect':'erased','erase_disclosure':'Full factory image at offset 0 erases saved settings and internal device data. Back up first. Transfer the complete external payload after flashing; external-volume survival is not assumed.','volume_effects':[{'volume':'application-content','effect':'unknown','evidence':evidence}],'evidence':evidence}
    results={}
    for mode in ('create','replace'):
        payload={'id':'waveshare-lora-0.1.17','owner':'waveshare-lora-companion','volumes':[{'id':'application-content','consumer':consumer,'requirements':{'case_semantics':policy['namespace']['case_semantics'],'hierarchical':True,'operations':['stat','get','mkdir',mode],'path_encoding':'utf-8-exact'}}],'bindings':[binding],'directories':[{'volume':'application-content','path':p,'operation':'ensure-directory'} for p in ('/Apps','/Apps/lora_messages')],'files':[{'volume':'application-content','destination':'/'+n,'source':'payload/'+n,'operation':mode,'owner':'waveshare-lora-companion','previous':None,**record(b)} for n,b in sorted(files.items())],'totals':{'file_count':len(files),'bytes':sum(map(len,files.values()))}}
        payload['inventory_sha256']=v.inventory_hash(payload)
        manifest={'schema_version':'1.0.0','container_format':'risc-catalog-payload-zip-store-v1','fixture':False,'description':'Software-qualified .55 full factory plus existing complete LoRa .17 companion. Unpublished candidate; hardware and X4 rollout gates remain. Explicit '+mode+' selected per file.','catalog_release':{'id':catalog['id'],'revision':catalog['revision'],'repository':REPO,'release_id':str(published['id']),'tag':TAG,'source_commit':PRODUCT},'product':{'id':board['board_id'],'hardware_profiles':['waveshare'],'hardware_revisions':[board['revision']],'storage_abi':'RiscStorageFilesV1','wire_protocol':'RTEF1','serial_contract_version':'1.0.0'},'firmware':{'id':TAG,'version':'0.1.55','source_commit':PRODUCT,'artifacts':[{'id':'factory-image','source':'firmware/'+FACTORY,**record(factory)}],'install':install},'payload':payload,'plan':{'purpose':'bootstrap','order':['firmware','payload','verify'],'pre_firmware_id':None,'policy':{'completion':'all-required-files-readable-by-target-consumer','on_partial_file':'retain-and-reconcile-selected-file','on_uncertain_result':'stop-inspect-no-automatic-retry','replacement':'explicit-selected-file-in-place-nonatomic','rollback':'none','unrelated_files':'preserve','verification':'commit-crc32-then-full-sha256-readback'}}}
        contents={'firmware/'+FACTORY:factory,**{'payload/'+n:b for n,b in files.items()}}
        raw=v.pack(manifest,contents)
        # Pins bind reviewed producer output for later catalog admission. They
        # are not accepted from a downloaded/untrusted manifest at installation.
        context={'context_version':'1.0.0','fixture':False,'product_id':policy['product_id'],'hardware_profile':'waveshare','hardware_revision':policy['hardware_revision'],'installed_firmware_id':None,'supported_methods':policy['supported_methods'],'namespaces':[{'firmware_id':TAG,**policy['namespace']}],'limits':policy['limits'],'trusted_manifest_sha256':sha(v.canonical(manifest)),'trusted_container_sha256':sha(raw),'trusted_binding_sha256':[sha(v.canonical(binding))],'trusted_consumer_sha256':[sha(v.canonical(consumer))],'trusted_install_sha256':sha(v.canonical(install))}
        dest=output/mode;dest.mkdir(parents=True,exist_ok=True)
        stem='Waveshare-0.1.55-LoRa-0.1.17-'+mode
        (dest/(stem+'.zip')).write_bytes(raw);(dest/(stem+'.json')).write_bytes(v.canonical(manifest));(dest/'context.json').write_bytes(v.canonical(context))
        descriptor={'schema_version':'1.0.0','manifest':{'asset_name':stem+'.json',**record(v.canonical(manifest))},'container':{'asset_name':stem+'.zip',**record(raw)}}
        v.schema_check(descriptor,'descriptor.schema.json');(dest/'descriptor.json').write_bytes(v.canonical(descriptor))
        results[mode]=v.validate_container(dest/(stem+'.zip'),context)
        require(raw==v.pack(manifest,dict(reversed(list(contents.items())))),'Non-deterministic container')
    (output/'qualification.json').write_bytes(v.canonical({'results':results,'publication_enabled':False,'hardware_tested':False,'live_capacity_verified':False,'policy_sha256':sha((DATA/'product-admission.json').read_bytes()),'schema_revision':SCHEMA,'runtime_revision':RUNTIME,'producer_revision':PRODUCT}))
    return results
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('assets','companion','runtime','schema','output'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();print(json.dumps(build(a.assets,a.companion,a.runtime,a.schema,a.output),indent=2))
