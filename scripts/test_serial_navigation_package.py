#!/usr/bin/env python3
"""Fail-closed .62 candidate pins and exact .61 retention tests."""
import argparse
import copy
import json
from pathlib import Path
import sys
import unittest
import tempfile
from unittest.mock import patch
import package_serial_navigation as p


class Contract(unittest.TestCase):
    def test_reservation(self):
        pins = p.pins()
        self.assertEqual(pins['version'], '0.1.62')
        self.assertIn('/0.1.62/', pins['feed_url'])
        self.assertEqual(p.REPLACEMENTS, {'default.elf', 'default.json', 'installed-apps/driver.elf'})

    def test_unqualified_pin_rejected(self):
        candidate = dict(p.pins(), finalized=False, runtime_revision=None)
        with tempfile.TemporaryDirectory() as tmp:
            docs = Path(tmp)
            (docs/'source-pins.json').write_bytes(p.encoded(candidate))
            with patch.object(p, 'DOCS', docs), self.assertRaisesRegex(ValueError, 'Qualified Runtime pin'):
                p.pins(final=True)


class Replay(unittest.TestCase):
    before = None

    def setUp(self):
        if self.before is None:
            self.skipTest('Exact public .61 inputs not supplied')

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
        with self.assertRaisesRegex(ValueError, 'Public .61 inventory'):
            self.compose(before=dict(self.before, **{'settings.elf': b'changed'}))

    def test_bad_external_byte(self):
        with self.assertRaisesRegex(ValueError, 'Public .61 SD inventory'):
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
        with self.assertRaisesRegex(ValueError, 'Public .61 inventory'):
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

    def test_home_replacements_leave_every_other_byte_exact(self):
        replacements={'default.elf':b'qualified-home-elf','default.json':b'qualified-home-manifest','installed-apps/driver.elf':b'qualified-url-only-driver'}
        pins=dict(p.pins(),store_replacements={name:p.record(value) for name,value in replacements.items()})
        after,payload,receipt=self.compose(p=pins,replacements=replacements)
        self.assertEqual(receipt['changed_store_files'],['cohort.json','default.elf','default.json','installed-apps/driver.elf'])
        self.assertEqual(payload,self.payload)
        for name,data in self.before.items():
            if name not in replacements and name!='cohort.json':self.assertEqual(after[name],data)

    def test_deterministic_packing(self):
        from current_bootfs import build
        from read_only_spiffs import read_image
        after, _, _ = self.compose()
        raw, receipt = build(after, size=0x550000)
        self.assertEqual(raw, build(dict(reversed(list(after.items()))), size=0x550000)[0])
        self.assertEqual(read_image(raw, 0x550000), after)
        self.assertGreaterEqual(receipt['empty_blocks'], 4)
        print('RETENTION_ONLY_PACKING ' + json.dumps(receipt, sort_keys=True))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--baseline-store', type=Path)
    parser.add_argument('--companion', type=Path)
    args, extra = parser.parse_known_args()
    if args.baseline_store or args.companion:
        assert args.baseline_store and args.companion
        from read_only_spiffs import read_image
        c = p.baseline_contract()
        raw = args.baseline_store.read_bytes()
        assert p.record(raw) == c['store']
        Replay.before = read_image(raw, 0x550000)
        Replay.payload = p.companion_files(args.companion, c)
    unittest.main(argv=[sys.argv[0], *extra])
