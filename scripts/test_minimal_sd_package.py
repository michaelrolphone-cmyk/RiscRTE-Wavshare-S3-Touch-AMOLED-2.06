#!/usr/bin/env python3
"""Placement contract tests; optional replay uses exact public .56 bytes."""
import argparse
import copy
import json
from pathlib import Path
import sys
import unittest
import package_minimal_sd as p

class Paths(unittest.TestCase):
    def test_accept(self):
        for value in ('Apps/calculator/calculator.elf', 'Apps/watch-bringup/manifest.json', 'suite-card.json'):
            p.external_path(value)
    def test_reject(self):
        for value in ('/Apps/x', 'Apps/../x', 'Apps//x', 'Apps/./x', 'Apps/a.', 'Apps/a ', 'Apps/a:b', 'Apps/a\\b', 'Apps/a*', 'Apps/a?', 'Apps/a"', 'Apps/a<', 'Apps/a>', 'Apps/a|', 'Apps/'+'x'*128, 'Apps/é'):
            with self.subTest(value=value), self.assertRaises(ValueError): p.external_path(value)
    def test_source_scope(self):
        pins=p.pins();self.assertEqual(pins['version'],'0.1.57');self.assertIn('/0.1.57/',pins['feed_url'])
        self.assertEqual(len(p.CORE),5)

class Replay(unittest.TestCase):
    before=None
    def setUp(self):
        if self.before is None:self.skipTest('Exact public inputs not supplied')
    def compose(self,**change):
        inputs=dict(before=self.before,companion=self.companion,replacements={},p=dict(p.pins(),store_replacements={}),revision='1'*40)
        inputs.update(change);return p.compose(**inputs)
    def test_exact_split(self):
        after,payload,receipt=self.compose()
        self.assertEqual((len(after),len(payload)),(111,45))
        self.assertFalse(json.loads(after['clock.json'])['launcher_visible'])
        self.assertEqual(receipt['external_apps'],22)
        for name, app in p.baseline_contract()['applications'].items():
            if name in p.CORE:self.assertIn(app['elf'],after)
            else:self.assertNotIn(app['elf'],after);self.assertIn(app['image_path'],payload)
        self.assertEqual(receipt['changed_store_files'],['boot.json','clock.json','cohort.json'])
    def test_no_mutation(self):
        before=dict(self.before);companion=dict(self.companion);self.compose()
        self.assertEqual(before,self.before);self.assertEqual(companion,self.companion)
    def test_bad_baseline(self):
        bad=dict(self.before,**{'settings.elf':b'changed'})
        with self.assertRaisesRegex(ValueError,'Public .56 inventory'):self.compose(before=bad)
    def test_missing_payload(self):
        with self.assertRaisesRegex(ValueError,'Companion inventory'):self.compose(companion={})
    def test_unapproved_rebuild(self):
        with self.assertRaisesRegex(ValueError,'Replacement scope'):self.compose(replacements={'settings.elf':b'new'})
    def test_wrong_replacement_hash(self):
        pins=dict(p.pins(),store_replacements={'default.elf':p.record(b'expected')})
        with self.assertRaisesRegex(ValueError,'Replacement digest'):self.compose(p=pins,replacements={'default.elf':b'wrong'})
    def test_deterministic_packing(self):
        from current_bootfs import build
        from read_only_spiffs import read_image
        after,_,_=self.compose();raw,receipt=build(after,size=0x550000)
        self.assertEqual(raw,build(dict(reversed(list(after.items()))),size=0x550000)[0]);self.assertEqual(read_image(raw,0x550000),after)
        self.assertGreaterEqual(receipt['empty_blocks'],4)
        print('PLACEMENT_ONLY_PACKING '+json.dumps(receipt,sort_keys=True))

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--baseline-store',type=Path);parser.add_argument('--companion',type=Path)
    args,extra=parser.parse_known_args()
    if args.baseline_store or args.companion:
        assert args.baseline_store and args.companion
        from read_only_spiffs import read_image
        c=p.baseline_contract();raw=args.baseline_store.read_bytes();assert p.record(raw)==c['store']
        Replay.before=read_image(raw,0x550000);Replay.companion=p.companion_files(args.companion,c)
    unittest.main(argv=[sys.argv[0],*extra])
