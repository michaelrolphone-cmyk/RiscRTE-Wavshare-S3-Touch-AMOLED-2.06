#!/usr/bin/env python3
"""Strict Wi-Fi store scope and synthetic mutation controls."""
import copy
import json
import unittest
from unittest.mock import patch
import package_wifi_footer as package


class WifiPackage(unittest.TestCase):
    def test_exact_recipe(self):
        p=package.pins();c=package.baseline_contract(p)
        self.assertEqual((p['version'],c['version'],c['elf_count'],len(c['files'])),('0.1.55','0.1.54',62,128))
        self.assertEqual(p['changed_store_files'],['cohort.json','wifi_settings.elf','wifi_settings.json'])
        self.assertEqual(c['files']['default.elf']['sha256'],p['default_sha256'])
        self.assertEqual(c['source_revision'],'55ba8842a28018bf2ae539f51c6ec2b2622e8a80')
        self.assertIsInstance(p['publication_enabled'],bool)
        self.assertEqual(p['power_provider']['version'],'0.1.3')
        self.assertRegex(p['power_provider']['elf_sha256'],r'^[0-9a-f]{64}$')

    def fixture(self):
        old={'id':'waveshare-power','version':'0.1.3','requires':[{'capability':'hardware.device','api':1}]}
        new=package.encoded(dict(old,version='0.1.3'))
        before={'default.elf':b'old-home','default.json':b'old-home-manifest','boot.json':b'unchanged-boot',
            'cohort.json':package.encoded({'version':'0.1.54','store_abi':3}),
            'battery/driver.elf':b'new-power','battery/manifest.json':package.encoded(old),
            'alarm-service/driver.elf':b'alarm','settings.elf':b'settings','springboard.elf':b'springboard','wifi_settings.elf':b'old-wifi','wifi_settings.json':package.encoded({'id':'wifi_settings','version':'1.1.33','requires':[]})}
        wifi=b'new-wifi';wifi_manifest=package.encoded({'id':'wifi_settings','version':'1.1.34','requires':[]})
        p={'version':'0.1.55','wifi_package':{'elf':package.record(wifi),'manifest':package.record(wifi_manifest)},'default_bytes':len(before['default.elf']),'default_sha256':package.sha(before['default.elf']),
            'default_manifest_sha256':package.sha(before['default.json']),
            'power_provider':{'version':'0.1.3','elf_bytes':len(b'new-power'),'elf_sha256':package.sha(b'new-power'),'manifest_sha256':package.sha(new)}}
        return before,before['default.elf'],before['default.json'],p,'1'*40,b'RISC_RUNTIME_VERSION:0.4.6\0',b'new-power',new,wifi,wifi_manifest

    def test_scope_and_all_file_mutations(self):
        with patch.object(package,'ALARM_SHA',package.sha(b'alarm')):
            args=self.fixture();before=args[0];after=package.compose(*args)
            self.assertEqual([n for n in sorted(after) if after[n]!=before[n]],package.CHANGED)
            verify=lambda changed:package.verify_store(before,changed,*args[1:])
            proof=verify(after);self.assertEqual(proof['unchanged_elf_count'],5)
            for name in after:
                with self.subTest(name=name),self.assertRaises((ValueError,json.JSONDecodeError)):
                    bad=dict(after);bad[name]+=b'!';verify(bad)
            for name in after:
                with self.subTest(missing=name),self.assertRaises(ValueError):
                    bad=dict(after);del bad[name];verify(bad)
            with self.assertRaises(ValueError):verify(dict(after,extra=b'extra'))
            for field,value in [('version','0.1.4'),('id','other'),('requires',[])]:
                with self.subTest(manifest=field),self.assertRaises(ValueError):
                    mutant=list(args);m=json.loads(mutant[7]);m[field]=value;mutant[7]=package.encoded(m)
                    mutant[3]=copy.deepcopy(mutant[3]);mutant[3]['power_provider']['manifest_sha256']=package.sha(mutant[7]);package.compose(*mutant)

    def test_wifi_authority_and_digest_guards(self):
        with patch.object(package,'ALARM_SHA',package.sha(b'alarm')):
            args=self.fixture()
            for field,value in [('version','1.1.35'),('id','other'),('requires',[{'capability':'private'}])]:
                bad=list(args);manifest=json.loads(bad[9]);manifest[field]=value;bad[9]=package.encoded(manifest)
                bad[3]=copy.deepcopy(bad[3]);bad[3]['wifi_package']['manifest']=package.record(bad[9])
                with self.subTest(field=field),self.assertRaises(ValueError):package.compose(*bad)
            for index in (8,9):
                bad=list(args);bad[index]+=b'!'
                with self.subTest(index=index),self.assertRaises(ValueError):package.compose(*bad)

    def test_cohort_binding(self):
        args=self.fixture();cohort=package.expected_cohort(args[0],args[3],args[4],args[5])
        self.assertEqual(cohort['firmware_sha256'],package.sha(args[5]));self.assertEqual(cohort['store_abi'],3)
        for firmware in (b'no-marker',args[5]*2):
            with self.assertRaises(ValueError):package.expected_cohort(args[0],args[3],args[4],firmware)

if __name__=='__main__':unittest.main(verbosity=2)
