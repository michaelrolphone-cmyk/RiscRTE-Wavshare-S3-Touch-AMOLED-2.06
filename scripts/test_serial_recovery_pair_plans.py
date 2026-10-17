#!/usr/bin/env python3
"""Static per-file plan guards; no catalog or device operations."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from build_serial_recovery_pair import PAIR_MODES,payload_entries,release_identity,verify_public_base,REPOSITORY
from package_serial_recovery import record, DOCS
from publish_serial_recovery_release import pair_asset_names

class Plans(unittest.TestCase):
    def setUp(self):
        self.files={f'Apps/example{i}/example.elf':bytes([i])*32 for i in range(45)}
        self.previous={name:record(data) for name,data in list(self.files.items())[:3]}
    def test_all_three_explicit_plans(self):
        for mode in PAIR_MODES:
            rows=payload_entries(self.files,mode,self.previous)
            self.assertEqual(len(rows),45)
            self.assertEqual(sum(r['operation']=='replace' for r in rows),{'create':0,'replace':45,'known-lora':3}[mode])
            for row in rows:
                name=row['destination'].removeprefix('/')
                self.assertEqual(row['previous'],self.previous[name] if mode=='known-lora' and name in self.previous else None)
                self.assertEqual({k:row[k] for k in ('bytes','sha256')},record(self.files[name]))
    def test_historical_hash_and_bytes_required(self):
        for field,value in [('sha256','0'*64),('bytes',31)]:
            history=copy.deepcopy(self.previous);history[next(iter(history))][field]=value
            with self.assertRaises(ValueError):payload_entries(self.files,'known-lora',history)
    def test_missing_historical_target_rejected(self):
        files=dict(self.files);del files[next(iter(self.previous))]
        with self.assertRaises(ValueError):payload_entries(files,'known-lora',self.previous)
    def test_unknown_or_automatic_mode_rejected(self):
        for mode in ['upsert','automatic','mixed','']:
            with self.assertRaises(ValueError):payload_entries(self.files,mode,self.previous)
    def test_canonical_extension_is_exact(self):
        names=pair_asset_names('0.1.58');self.assertEqual(len(names),14)
        self.assertIn('Waveshare-0.1.58-SD-Apps-known-lora.zip',names)
        self.assertEqual(sum(n.endswith('.zip') for n in names),3)
    def test_public_057_historical_guard_map(self):
        contract=json.loads((DOCS/'baseline-0.1.57.json').read_bytes())
        historical=contract['historical_external_companion']['files']
        self.assertEqual(len(historical),3)
        self.assertEqual({name:contract['external_files'][name] for name in historical},historical)
    def test_create_once_real_release_identity(self):
        p={'release_tag':'test-sd-apps-0.1.58'}
        metadata=dict(id=123,draft=False,prerelease=True,tag_name=p['release_tag'],target_commitish='1'*40)
        self.assertEqual(release_identity(metadata,p,1),'1'*40)
        for key,value in [('id',0),('id',True),('id','123'),('draft',True),('prerelease',False),
                          ('tag_name','test-sd-apps-0.1.57'),('target_commitish','main')]:
            with self.subTest(key=key,value=value),self.assertRaises(ValueError):
                release_identity(dict(metadata,**{key:value}),p,1)
        for revision in (0,2,True,'1'):
            with self.subTest(revision=revision),self.assertRaises(ValueError):
                release_identity(metadata,p,revision)
    def test_public_base_assets_have_exact_custody(self):
        tag='test-sd-apps-0.1.58';data=b'qualified base';name='release.json'
        row=dict(name=name,state='uploaded',size=len(data),digest='sha256:'+record(data)['sha256'],
                 browser_download_url='https://github.com/'+REPOSITORY+'/releases/download/'+tag+'/'+name)
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);(root/name).write_bytes(data)
            verify_public_base(root,{'assets':[row]},tag)
            for key,value in [('size',0),('digest','sha256:'+'0'*64),('state','new'),
                              ('browser_download_url','https://example.test/release.json')]:
                with self.subTest(key=key),self.assertRaises(ValueError):
                    verify_public_base(root,{'assets':[dict(row,**{key:value})]},tag)
            for rows in ([],[row,row]):
                with self.assertRaises(ValueError):verify_public_base(root,{'assets':rows},tag)

if __name__=='__main__':unittest.main()
