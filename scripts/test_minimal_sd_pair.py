#!/usr/bin/env python3
"""Run real-candidate rejection and profile invariants (no device operations)."""
import argparse,copy,importlib.util,json,tempfile,zipfile
from pathlib import Path

def main():
 p=argparse.ArgumentParser();p.add_argument('--candidate',type=Path,required=True);p.add_argument('--schema',type=Path,required=True);a=p.parse_args()
 spec=importlib.util.spec_from_file_location('validator',a.schema/'validate.py');v=importlib.util.module_from_spec(spec);spec.loader.exec_module(v)
 accepted=[]
 for mode in ('create','replace','known-lora'):
  d=a.candidate/mode;m=json.loads(next(d.glob('Waveshare*.json')).read_bytes());c=json.loads((d/'context.json').read_bytes());z=next(d.glob('*.zip'));v.validate_container(z,c)
  assert m['product']['hardware_revisions']==['unspecified'];assert m['payload']['totals']=={'bytes':3113484,'file_count':45}
  if mode=='known-lora':
   replaced=[f for f in m['payload']['files'] if f['operation']=='replace'];created=[f for f in m['payload']['files'] if f['operation']=='create']
   assert len(replaced)==3 and len(created)==42
   assert all(f['previous']=={k:f[k] for k in ('bytes','sha256')} for f in replaced)
   assert all(f['previous'] is None for f in created)
  else:assert all(f['operation']==mode for f in m['payload']['files'])
  assert m['plan']['order']==['firmware','payload','verify']
  assert len(m['firmware']['artifacts'])==1 and m['firmware']['artifacts'][0]['bytes']==16777216
  assert {b['namespace_id'] for b in m['payload']['bindings']}=={'12'}
  assert c['namespaces'][0]['write_budget_bytes']==3113484 and c['namespaces'][0]['max_file_bytes']==288112
  def reject(label,mutate,repin=False):
   mm,cc=copy.deepcopy(m),copy.deepcopy(c);mutate(mm,cc)
   if repin:
    mm['payload']['inventory_sha256']=v.inventory_hash(mm['payload']);cc['trusted_manifest_sha256']=v.sha256(v.canonical(mm))
   try:v.validate_manifest(mm,cc)
   except v.Invalid:accepted.append(mode+':'+label)
   else:raise AssertionError('Accepted invalid '+label)
  reject('wrong-board',lambda m,c:c.update(hardware_revision='rev-a'))
  reject('private-ingress',lambda m,c:m['payload']['bindings'][0].update(namespace_id='2'),True)
  reject('unsupported-method',lambda m,c:c.update(supported_methods=['not-supported']))
  reject('insufficient-budget',lambda m,c:c['namespaces'][0].update(write_budget_bytes=3113483))
  reject('file-ceiling',lambda m,c:c['namespaces'][0].update(max_file_bytes=288111))
  reject('read-only',lambda m,c:c['namespaces'][0].update(writable=False))
  reject('name-mode-mismatch',lambda m,c:c['namespaces'][0].update(case_semantics='sensitive'))
  reject('missing-mkdir',lambda m,c:c['namespaces'][0].update(operations=['stat','get','create','replace']))
  reject('payload-first-factory',lambda m,c:m['plan'].update(order=['payload','firmware','verify']),True)
  reject('foreign-owner',lambda m,c:m['payload']['files'][0].update(owner='other-owner'),True)
  reject('traversal',lambda m,c:m['payload']['files'][0].update(destination='/Apps/../other'),True)
  reject('trailing-dot',lambda m,c:m['payload']['files'][0].update(destination='/Apps/lora_messages/bad.'),True)
  reject('too-long-path',lambda m,c:c['namespaces'][0].update(max_path_bytes=8))
  reject('unknown-field',lambda m,c:m.update(unrecognized=True),True)
  with tempfile.TemporaryDirectory() as temp:
   broken=Path(temp)/'bad.zip';raw=bytearray(z.read_bytes());raw[len(raw)//2]^=1;broken.write_bytes(raw)
   cc=copy.deepcopy(c);cc['trusted_container_sha256']=v.sha256(raw)
   try:v.validate_container(broken,cc)
   except (v.Invalid,zipfile.BadZipFile):accepted.append(mode+':modified-container-byte')
   else:raise AssertionError('Accepted modified container')
 print(json.dumps({'status':'passed','positive_candidates':3,'rejection_count':len(accepted),'rejections':accepted,'hardware_tested':False},indent=2))
if __name__=='__main__':main()
