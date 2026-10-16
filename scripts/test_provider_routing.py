#!/usr/bin/env python3
"""Guard specialized test dispatch and deterministic SDK collision handling."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
import prepare_provider_test_sdk as sdk
import test_drivers


class Routing(unittest.TestCase):
    def test_all_storage_integrations_have_dedicated_runners(self):
        self.assertEqual(set(test_drivers.SPECIALIZED), {
            'test_storage', 'test_storage_async', 'test_storage_export', 'test_usb_storage'})
        standalone = {p.stem for p in test_drivers.standalone_sources()}
        self.assertFalse(standalone & test_drivers.SPECIALIZED.keys())
        for test, runner in test_drivers.SPECIALIZED.items():
            self.assertTrue((test_drivers.ROOT / 'tests' / (test + '.c')).is_file())
            self.assertTrue((test_drivers.ROOT / 'scripts' / runner).is_file())
        self.assertEqual(standalone | test_drivers.SPECIALIZED.keys(), {
            p.stem for p in (test_drivers.ROOT / 'tests').glob('test_*.c')})

    def test_workflow_pins_match_header_review(self):
        spec = json.loads((test_drivers.ROOT / 'docs/provider-ci/header-overrides.json').read_text())
        workflow = (test_drivers.ROOT / '.github/workflows/providers.yml').read_text()
        for name in ('watch_revision', 'runtime_revision'):
            self.assertIn('ref: ' + spec[name], workflow)
        self.assertIn('contents: read', workflow)

    def test_all_dedicated_runners_are_in_ci_normal_and_sanitized(self):
        workflow = (test_drivers.ROOT / '.github/workflows/providers.yml').read_text()
        for runner in test_drivers.SPECIALIZED.values():
            lines = [line for line in workflow.splitlines() if 'scripts/' + runner + ' ' in line]
            self.assertEqual(len(lines), 2, runner)
            self.assertEqual(sum('--sanitize' in line for line in lines), 1, runner)


class Headers(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for owner in ('watch', 'runtime'):
            (self.root / owner / 'sdk').mkdir(parents=True)
        self.sources = [(owner, self.root / owner, ['sdk']) for owner in ('watch', 'runtime')]
        self.out = self.root / 'out'

    def write(self, owner, data):
        path = self.root / owner / 'sdk/Header.h'
        path.write_bytes(data)
        return {'owner': owner, 'path': 'sdk/Header.h', 'sha256': hashlib.sha256(data).hexdigest()}

    def test_identical_duplicate_allowed(self):
        for owner in ('watch', 'runtime'):
            self.write(owner, b'same')
        proof = sdk.assemble(self.sources, {}, self.out)
        self.assertEqual(proof['headers']['Header.h']['owner'], 'runtime')
        self.assertEqual((self.out / 'Header.h').read_bytes(), b'same')

    def test_explicit_override_exact_bytes(self):
        old, new = self.write('watch', b'old'), self.write('runtime', b'new')
        proof = sdk.assemble(self.sources, {'Header.h': {'previous': old, 'selected': new}}, self.out)
        self.assertEqual((self.out / 'Header.h').read_bytes(), b'new')
        self.assertEqual(len(proof['overrides']), 1)

    def test_unreviewed_collision_rejected(self):
        self.write('watch', b'old'); self.write('runtime', b'new')
        with self.assertRaisesRegex(ValueError, 'override closure'):
            sdk.assemble(self.sources, {}, self.out)
        self.assertFalse(self.out.exists())

    def test_wrong_hash_rejected(self):
        old, new = self.write('watch', b'old'), self.write('runtime', b'new')
        new['sha256'] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'override closure'):
            sdk.assemble(self.sources, {'Header.h': {'previous': old, 'selected': new}}, self.out)

    def test_stale_override_rejected(self):
        self.write('runtime', b'new')
        with self.assertRaisesRegex(ValueError, 'override closure'):
            sdk.assemble(self.sources, {'removed': {}}, self.out)

    def test_nonempty_destination_rejected(self):
        self.out.mkdir(); (self.out / 'stale').write_text('stale')
        with self.assertRaisesRegex(ValueError, 'must be empty'):
            sdk.assemble(self.sources, {}, self.out)


if __name__ == '__main__':
    unittest.main()
