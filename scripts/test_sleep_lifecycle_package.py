#!/usr/bin/env python3
"""Strict Runtime-only store scope; synthetic mutations, never hardware proof."""
import copy
import json
import unittest
from unittest.mock import patch
import package_sleep_lifecycle as package


class SleepPackage(unittest.TestCase):
    def test_exact_recipe(self):
        p=package.pins();c=package.baseline_contract(p)
        self.assertEqual((p['version'],c['version'],c['elf_count'],len(c['files'])),('0.1.54','0.1.53',62,128))
        self.assertEqual(p['changed_store_files'],['cohort.json'])
        self.assertEqual(c['files']['default.elf']['sha256'],p['default_sha256'])
        self.assertEqual(c['source_revision'],'4b5d88ee508960199ec70e00daaba49134021d3a')
        self.assertTrue(p['publication_enabled'])
        self.assertEqual(p['power_provider']['version'],'0.1.3')
        self.assertRegex(p['power_provider']['elf_sha256'],r'^[0-9a-f]{64}$')

    def fixture(self):
        old={'id':'waveshare-power','version':'0.1.3','requires':[{'capability':'hardware.device','api':1}]}
        new=package.encoded(dict(old,version='0.1.3'))
        before={'default.elf':b'old-home','default.json':b'old-home-manifest','boot.json':b'unchanged-boot',
            'cohort.json':package.encoded({'version':'0.1.53','store_abi':3}),
            'battery/driver.elf':b'new-power','battery/manifest.json':package.encoded(old),
            'alarm-service/driver.elf':b'alarm','settings.elf':b'settings','springboard.elf':b'springboard'}
        p={'version':'0.1.54','default_bytes':len(before['default.elf']),'default_sha256':package.sha(before['default.elf']),
            'default_manifest_sha256':package.sha(before['default.json']),
            'power_provider':{'version':'0.1.3','elf_bytes':len(b'new-power'),'elf_sha256':package.sha(b'new-power'),'manifest_sha256':package.sha(new)}}
        return before,before['default.elf'],before['default.json'],p,'1'*40,b'RISC_RUNTIME_VERSION:0.4.6\0',b'new-power',new

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
                    mutant=list(args);m=json.loads(mutant[-1]);m[field]=value;mutant[-1]=package.encoded(m)
                    mutant[3]=copy.deepcopy(mutant[3]);mutant[3]['power_provider']['manifest_sha256']=package.sha(mutant[-1]);package.compose(*mutant)

    def test_cohort_binding(self):
        args=self.fixture();cohort=package.expected_cohort(args[0],args[3],args[4],args[5])
        self.assertEqual(cohort['firmware_sha256'],package.sha(args[5]));self.assertEqual(cohort['store_abi'],3)
        for firmware in (b'no-marker',args[5]*2):
            with self.assertRaises(ValueError):package.expected_cohort(args[0],args[3],args[4],firmware)

if __name__=='__main__':unittest.main(verbosity=2)
