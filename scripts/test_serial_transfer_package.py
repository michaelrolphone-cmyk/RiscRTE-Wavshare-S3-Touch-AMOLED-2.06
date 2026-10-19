#!/usr/bin/env python3
"""Fail-closed .64 candidate pins and exact .63 retention tests."""
import argparse
import copy
import json
from pathlib import Path
import sys
import unittest
import tempfile
from unittest.mock import patch
import package_serial_transfer as p


class Contract(unittest.TestCase):
    def test_reservation(self):
        pins = p.pins()
        self.assertEqual(pins['version'], '0.1.64')
        self.assertIn('/0.1.64/', pins['feed_url'])
        self.assertEqual(p.REPLACEMENTS, {'default.elf','default.json','installed-apps/driver.elf'})

    def test_unqualified_pin_rejected(self):
        candidate = dict(p.pins(), finalized=False, runtime_revision=None)
        with tempfile.TemporaryDirectory() as tmp:
            docs = Path(tmp)
            (docs/'source-pins.json').write_bytes(p.encoded(candidate))
            with patch.object(p, 'DOCS', docs), self.assertRaisesRegex(ValueError, 'Qualified Runtime pin'):
                p.pins(final=True)


class Replay(unittest.TestCase):
    before = None
    selected_inputs = None

    def setUp(self):
        if self.before is None:
            self.skipTest('Exact public .63 inputs not supplied')

    def compose(self, **change):
        inputs = dict(before=self.before, companion=self.payload, replacements={},
                      p=dict(p.pins(), store_replacements={}), revision='1' * 40)
        inputs.update(change)
        return p.compose(**inputs)

    def test_exact_retention(self):
        after, payload, receipt = self.compose()
        self.assertEqual(receipt['changed_store_files'], ['cohort.json'])
        self.assertEqual(receipt['moved_elfs'], [])
        self.assertEqual(payload, self.payload)
        self.assertEqual(after['boot.json'], self.before['boot.json'])
        self.assertEqual((len(after), len(payload)), (111, 45))
        for name, data in self.before.items():
            if name != 'cohort.json':
                self.assertEqual(after[name], data)

    def test_inputs_unchanged(self):
        before, payload = copy.deepcopy(self.before), copy.deepcopy(self.payload)
        self.compose()
        self.assertEqual((self.before, self.payload), (before, payload))

    def test_bad_internal_byte(self):
        with self.assertRaisesRegex(ValueError, 'Public .63 inventory'):
            self.compose(before=dict(self.before, **{'settings.elf': b'changed'}))

    def test_bad_external_byte(self):
        with self.assertRaisesRegex(ValueError, 'Public .63 SD inventory'):
            self.compose(companion=dict(self.payload, **{next(iter(self.payload)): b'changed'}))

    def test_wrong_replacement_hash(self):
        pins = dict(p.pins(), store_replacements={'installed-apps/driver.elf': p.record(b'expected')})
        with self.assertRaisesRegex(ValueError, 'Replacement digest'):
            self.compose(p=pins, replacements={'installed-apps/driver.elf': b'wrong'})

    def test_reject_unapproved_provider(self):
        pins = dict(p.pins(), store_replacements={'sd-volume/driver.elf': p.record(b'new')})
        with self.assertRaisesRegex(ValueError, 'Replacement scope'):
            self.compose(p=pins, replacements={'sd-volume/driver.elf': b'new'})

    def test_reject_boot_policy_change(self):
        changed = dict(self.before, **{'boot.json': b'{}'})
        with self.assertRaisesRegex(ValueError, 'Public .63 inventory'):
            self.compose(before=changed)

    def test_reject_every_packaged_replacement(self):
        for name in ('clock.elf','clock.json','installed-apps/manifest.json'):
            new=b'changed'; pins=dict(p.pins(),store_replacements={name:p.record(new)})
            with self.subTest(name=name), self.assertRaisesRegex(ValueError,'Replacement scope'):
                self.compose(p=pins,replacements={name:new})

    def test_only_catalog_url_replacement_allowed(self):
        name='installed-apps/driver.elf';new=b'versioned-catalog-test-only'
        pins=dict(p.pins(),store_replacements={name:p.record(new)})
        after,payload,receipt=self.compose(p=pins,replacements={name:new})
        self.assertEqual(receipt['changed_store_files'],['cohort.json',name])
        self.assertEqual(after['installed-apps/manifest.json'],self.before['installed-apps/manifest.json'])
        self.assertEqual(after['default.elf'],self.before['default.elf'])
        self.assertEqual(payload,self.payload)

    def test_deterministic_packing(self):
        from current_bootfs import build
        from read_only_spiffs import read_image
        after, _, _ = self.compose()
        raw, receipt = build(after, size=0x550000)
        self.assertEqual(raw, build(dict(reversed(list(after.items()))), size=0x550000)[0])
        self.assertEqual(read_image(raw, 0x550000), after)
        self.assertGreaterEqual(receipt['empty_blocks'], 4)
        print('RETENTION_ONLY_PACKING ' + json.dumps(receipt, sort_keys=True))

    def test_actual_selected_home_catalog_and_retained_payload(self):
        if self.selected_inputs is None:
            self.skipTest('Fresh selected target inputs not supplied')
        from build_serial_transfer_inputs import require_home, catalog_delta
        from current_bootfs import build
        from read_only_spiffs import read_image
        root = self.selected_inputs
        require_home(root / 'home-a'); require_home(root / 'home-b')
        replacements = {name:(root/path).read_bytes() for name,path in (
            ('default.elf','home-a/default.elf'),('default.json','home-a/default.json'),
            ('installed-apps/driver.elf','catalog/driver.elf'))}
        catalog_delta(self.before['installed-apps/driver.elf'],replacements['installed-apps/driver.elf'])
        after,payload,receipt = self.compose(p=p.pins(final=True),replacements=replacements)
        self.assertEqual(receipt['changed_store_files'],['cohort.json','default.elf','default.json','installed-apps/driver.elf'])
        self.assertEqual(payload,self.payload)
        for name,data in self.before.items():
            if name not in replacements and name!='cohort.json':self.assertEqual(after[name],data)
        packed,proof=build(after,size=0x550000)
        self.assertEqual(read_image(packed,0x550000),after)
        self.assertGreaterEqual(proof['empty_blocks'],4)
        print('SELECTED_INPUT_PACKING '+json.dumps(dict(packing=proof,preservation=receipt),sort_keys=True))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--baseline-store', type=Path)
    parser.add_argument('--companion', type=Path)
    parser.add_argument('--selected-inputs', type=Path)
    args, extra = parser.parse_known_args()
    if args.baseline_store or args.companion:
        assert args.baseline_store and args.companion
        from read_only_spiffs import read_image
        c = p.baseline_contract()
        raw = args.baseline_store.read_bytes()
        assert p.record(raw) == c['store']
        Replay.before = read_image(raw, 0x550000)
        Replay.payload = p.companion_files(args.companion, c)
        Replay.selected_inputs = args.selected_inputs
    unittest.main(argv=[sys.argv[0], *extra])
