#!/usr/bin/env python3
"""Attach only deterministic canonical sidecars to the exact .61 public release.

No catalog record is created here. Association requires exact returned catalog
identity and separate product context review after public-byte audit.
"""
import argparse
import json
from pathlib import Path
import subprocess
import tempfile
import time
from package_serial_lifetime import pins,require,sha,record,encoded
from publish_serial_lifetime_release import gh,find_release,check_tags,object_json,pair_asset_names
from build_serial_lifetime_pair import build,PAIR_MODES


def publish(assets,runtime,schema,work,revision):
    p=pins(final=True);repo='michaelrolphone-cmyk/RiscRTE-Wavshare-S3-Touch-AMOLED-2.06'
    require(p['publication_enabled'] is True,'Product release publication not selected')
    require(not work.exists(),'Pair publication work directory must be new');work.mkdir(parents=True)
    tag=object_json('api','repos/'+repo+'/git/ref/tags/'+p['release_tag'])
    require(check_tags([tag],p['release_tag'],p['version'],revision),'Published tag source differs')
    release=find_release(repo,p['release_tag']);require(release and not release['draft'] and release['target_commitish']==revision,'Public exact-source release required')
    metadata=work/'github-release.json';metadata.write_bytes(encoded(release))
    report=build(assets,metadata,runtime,schema,work/'candidate',catalog_revision=1)
    tests=subprocess.run(['python3',str(Path(__file__).with_name('test_serial_lifetime_pair.py')),'--candidate',str(work/'candidate'),'--schema',str(schema)],check=True,capture_output=True,text=True)
    (work/'pair-contract-tests.json').write_text(tests.stdout);report['contract_tests']=json.loads(tests.stdout)
    uploads=work/'uploads';uploads.mkdir();files={}
    for mode in PAIR_MODES:
        folder=work/'candidate'/mode;stem='Waveshare-'+p['version']+'-SD-Apps-'+mode
        for source,dest in ((stem+'.zip',stem+'.zip'),(stem+'.json',stem+'.json'),('context.json',stem+'-context.json'),('descriptor.json',stem+'-descriptor.json')):
            files[dest]=(folder/source).read_bytes()
    files['PAIR-QUALIFICATION.json']=encoded(report)
    files['PAIR-SHA256SUMS']=''.join(sha(data)+'  '+name+'\n' for name,data in sorted(files.items())).encode()
    require(set(files)==pair_asset_names(p['version']),'Canonical sidecar set differs')
    base_names={f.name for f in assets.iterdir()};expected=base_names|set(files)
    current={a['name']:a for a in release['assets']}
    require(len(current)==len(release['assets']) and set(current)<=expected,'Unexpected release asset prevents canonical extension')
    for name,data in files.items():
        target=uploads/name;target.write_bytes(data)
        if name in current:
            require(current[name]['size']==len(data) and current[name]['digest']=='sha256:'+sha(data),'Existing canonical sidecar differs: '+name)
        else:
            gh('release','upload',p['release_tag'],str(target),'--repo',repo)
    final=None
    for pause in (0,1,2,4):
        if pause:time.sleep(pause)
        final=find_release(repo,p['release_tag'])
        if final is not None and {a['name'] for a in final['assets']}==expected:break
    require(final and final['id']==release['id'] and final['target_commitish']==revision and
            final['tag_name']==p['release_tag'] and final['draft'] is False and final['prerelease'] is True,
            'Canonical release identity changed during publication')
    require(len(final['assets'])==len(expected) and {a['name'] for a in final['assets']}==expected,'Final canonical asset inventory not visible; resume same source only')
    all_files={f.name:f.read_bytes() for f in assets.iterdir()};all_files.update(files)
    with tempfile.TemporaryDirectory(prefix='wave-pair-public-') as tmp:
        for row in final['assets']:
            data=all_files[row['name']];require(row['state']=='uploaded' and row['size']==len(data) and row['digest']=='sha256:'+sha(data),'Final uploaded asset differs')
            gh('release','download',p['release_tag'],'--repo',repo,'--pattern',row['name'],'--dir',tmp)
            require((Path(tmp)/row['name']).read_bytes()==data,'Independent public readback differs: '+row['name'])
    receipt={'schema':1,'source_revision':revision,'github_release_id':final['id'],'tag':p['release_tag'],'canonical_assets':{n:record(b) for n,b in sorted(files.items())},'complete_public_asset_count':len(expected),'public_bytes_verified':True,'catalog_created':False,'catalog_identity_requires_readback':True,'hardware_tested':False}
    (work/'public-pair-audit.json').write_bytes(encoded(receipt));print(json.dumps(receipt,sort_keys=True));return receipt

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('assets','runtime','schema','work'):parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--source-revision',dest='revision',required=True)
    publish(**vars(parser.parse_args()))
