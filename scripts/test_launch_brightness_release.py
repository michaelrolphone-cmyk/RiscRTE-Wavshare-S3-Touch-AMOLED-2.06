#!/usr/bin/env python3
"""Negative gates for complete app-only launch-brightness packaging."""
import copy
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile
import package_launch_brightness as package
import qualify_launch_brightness as qualify
import stage_launch_baseline_native as staging


def elf(name):
    return b'\x7fELF\x01\x01\x01'+b'\0'*9+b'\x03\x00\x5e\x00'+name.encode()

class ReleaseTests(unittest.TestCase):
    def test_final_pins(self):
        package.verify_final_pins()

    def test_pin_rejections(self):
        mutations={'finalized':False,'publication_enabled':'true','version':'0.1.47','baseline_version':'0.1.46','baseline_tag':'bad','release_tag':'bad','system_revision':'0'*40,'adapter_revision':'0'*40,'runtime_revision':'0'*40,'baseline_product':'main','baseline_sha256':'pending','baseline_evidence_sha256':'pending','compiler_sha256':'pending','app_cohort_sha256':'0'*64,'native_changed':True,'changed_apps':[],'changed_store_files':[],'baseline_home_sha256':'0'*64}
        for name,value in mutations.items():
            with self.subTest(name=name),patch.dict(package.PINS,{name:value}):
                with self.assertRaises((ValueError,AssertionError)):
                    package.verify_final_pins()

    def test_complete_app_set_required(self):
        missing=dict(package.APPS);missing.pop('waterfall')
        with patch.object(package,'APPS',missing),self.assertRaises(ValueError):
            package.verify_final_pins()

    def test_patch_successor_only(self):
        apps=copy.deepcopy(package.APPS);apps['waterfall']['proposed_version']='9.9.9'
        with patch.object(package,'APPS',apps),self.assertRaises(ValueError):
            package.verify_final_pins()

    def test_exact_factory_required(self):
        with self.assertRaises(ValueError):
            package.verify_baseline_bytes(b'wrong')
        with self.assertRaises(ValueError):
            package.verify_baseline_bytes(b'\xff'*0x1000000)

    def fixture(self):
        rows={};before={'cohort.json':b'{"version":"0.1.47"}'};new={}
        for name in sorted(package.EXPECTED_APPS):
            old=b'old-'+name.encode();payload=elf(name)
            rows[name]={'sha256':package.sha(payload),'deployed_sha256':package.sha(old),'bytes':len(payload),'old_version':'0.1.9','proposed_version':'0.1.10'}
            before[name+'.elf']=old
            before[name+'.json']=json.dumps({'version':'0.1.9','name':name,'permissions':['display','read'], 'id':name}).encode()
            new[name]=payload
        for name in ['default','springboard']+['unchanged-'+str(i) for i in range(43)]:
            before[name+'.elf']=elf(name)
            before[name+'.json']=b'{"version":"0.16.0","permissions":["unchanged"]}'
        pins={**package.PINS,'baseline_home_sha256':package.sha(before['default.elf']),'baseline_springboard_sha256':package.sha(before['springboard.elf']),'baseline_springboard_manifest_sha256':package.sha(before['springboard.json'])}
        return before,new,rows,pins

    def candidate(self):
        before,new,rows,pins=self.fixture()
        with patch.object(package,'APPS',rows):
            store=package.replace_apps(before,new)
        store['cohort.json']=b'{"version":"0.1.48"}'
        return before,store,rows,pins

    def test_complete_version_only_replacement(self):
        before,store,rows,pins=self.candidate()
        with patch.object(package,'APPS',rows),patch.object(package,'PINS',pins):
            self.assertEqual(package.verify_changed_store(before,store),package.PINS['changed_store_files'])
        self.assertEqual(sum(x.endswith('.elf') for x in store),62)
        for name in rows:
            self.assertEqual(json.loads(store[name+'.json']),dict(json.loads(before[name+'.json']),version='0.1.10'))

    def test_replacement_rejections(self):
        for mutation in ('missing','extra','old-elf','old-version','new-hash','new-size','bad-elf'):
            before,new,rows,pins=self.fixture()
            name='alarms'
            if mutation=='missing':new.pop(name)
            elif mutation=='extra':new['extra']=elf('extra')
            elif mutation=='old-elf':before[name+'.elf']=b'wrong'
            elif mutation=='old-version':before[name+'.json']=b'{"version":"0.1.8"}'
            elif mutation=='new-hash':new[name]+=b'changed'
            elif mutation=='new-size':rows[name]['bytes']+=1
            elif mutation=='bad-elf':
                new[name]=b'bad-elf';rows[name].update(sha256=package.sha(new[name]),bytes=len(new[name]))
            with self.subTest(mutation=mutation),patch.object(package,'APPS',rows),patch.object(package,'PINS',pins):
                with self.assertRaises((ValueError,KeyError)):
                    package.replace_apps(before,new)

    def test_store_rejections(self):
        for mutation in ('removed','extra','unchanged-elf','home','springboard','manifest-authority','unchanged-cohort','missing-elf-count'):
            before,store,rows,pins=self.candidate()
            if mutation=='removed':store.pop('unchanged-0.json')
            elif mutation=='extra':store['extra.txt']=b'new'
            elif mutation=='unchanged-elf':store['unchanged-0.elf']=elf('changed')
            elif mutation=='home':store['default.elf']=elf('changed')
            elif mutation=='springboard':store['springboard.json']=b'{}'
            elif mutation=='manifest-authority':
                data=json.loads(store['alarms.json']);data['permissions'].append('write');store['alarms.json']=json.dumps(data).encode()
            elif mutation=='unchanged-cohort':store['cohort.json']=before['cohort.json']
            elif mutation=='missing-elf-count':
                before.pop('unchanged-0.elf');store.pop('unchanged-0.elf')
            with self.subTest(mutation=mutation),patch.object(package,'APPS',rows),patch.object(package,'PINS',pins):
                with self.assertRaises(ValueError):
                    package.verify_changed_store(before,store)

    def test_native_evidence_custody(self):
        firmware=b'exact-native';native_elf=elf('firmware');factory=bytearray(b'\xff'*0x1000000)
        factory[0x10000:0x10000+len(firmware)]=firmware
        metadata={'source_revision':package.PINS['baseline_product'],'runtime_revision':package.PINS['runtime_revision'],'version':'0.1.47'}
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'evidence.zip'
            with zipfile.ZipFile(path,'w') as archive:
                archive.writestr('release.json',json.dumps(metadata));archive.writestr('firmware.bin',firmware);archive.writestr('firmware.elf',native_elf)
            pins={**package.PINS,'baseline_sha256':package.sha(factory),'baseline_evidence_sha256':package.sha(path.read_bytes()),'baseline_native_sha256':package.sha(firmware),'baseline_native_elf_sha256':package.sha(native_elf)}
            with patch.object(package,'PINS',pins),patch.object(staging,'PINS',pins):
                files,receipt=staging.verified_native(factory,path)
                self.assertEqual(files['firmware.bin'],firmware)
                self.assertTrue(receipt['native_reused_unchanged'])
                for key in ('baseline_evidence_sha256','baseline_native_sha256','baseline_native_elf_sha256'):
                    with self.subTest(key=key),patch.dict(pins,{key:'0'*64}),self.assertRaises(ValueError):
                        staging.verified_native(factory,path)

    def test_result_matrices_reject_incomplete(self):
        with tempfile.TemporaryDirectory() as td:
            output=Path(td)
            for name in ('receipt.json','results.json','evidence.json'):
                value=[] if name=='results.json' else {'runs':[],'results':[]}
                (output/name).write_text(json.dumps(value))
            for label in ('custody','custody-baseline','brightness','brightness-baseline','springboard','rf-raster'):
                with self.subTest(label=label),self.assertRaises(ValueError):
                    qualify.verify_result(label,output)

if __name__=='__main__':
    unittest.main()
