#!/usr/bin/env python3
"""Candidate custody boundaries, separate from full production admission."""
import copy
import importlib.util
import json
import os
import shutil
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import qualify_t039_wave_product as q


class ProductCandidate(unittest.TestCase):
    def setUp(self):
        self.elf = b'candidate-elf'
        manifest = {'version': '0.1.29', 'file_name': 'ble_buttons.elf',
                    'requires': [{'capability': 'cap' + str(i), 'api': 1} for i in range(16)]}
        self.old_manifest = json.dumps(manifest).encode()
        manifest['version'] = '0.1.31'
        self.manifest = json.dumps(manifest).encode()
        self.pins = {'candidate_elf': q.record(self.elf), 'candidate_manifest': q.record(self.manifest),
                     'image_source': {'path': q.ELF, 'volume_instance': 12}}
        boot = {'app_capabilities': [{'manifest': 'ble_buttons.json',
                 'image_source': self.pins['image_source'], 'grants': [{} for _ in range(17)]}]}
        self.before = {'boot.json': json.dumps(boot).encode(), 'ble_buttons.json': self.old_manifest,
                       'default.elf': b'unchanged-home'}
        self.external = {q.ELF: b'old-elf', q.MIRROR: self.old_manifest, 'other.elf': b'unchanged'}

    def compose(self):
        return q.compose(self.before, self.external, self.elf, self.manifest, self.pins)

    def test_exact_delta_only(self):
        before, external = copy.deepcopy(self.before), copy.deepcopy(self.external)
        after, payload = self.compose()
        self.assertEqual(self.before, before); self.assertEqual(self.external, external)
        self.assertEqual(after['boot.json'], before['boot.json'])
        self.assertEqual(payload['other.elf'], external['other.elf'])
        self.assertEqual(after['ble_buttons.json'], payload[q.MIRROR])

    def test_candidate_elf_tamper(self):
        self.elf += b'x'
        with self.assertRaisesRegex(ValueError, 'input bytes'): self.compose()

    def test_candidate_manifest_tamper(self):
        self.manifest += b' '
        with self.assertRaisesRegex(ValueError, 'input bytes'): self.compose()

    def test_manifest_semantic_expansion(self):
        m = json.loads(self.manifest); m['entry'] = 'new_entry'
        self.manifest = json.dumps(m).encode(); self.pins['candidate_manifest'] = q.record(self.manifest)
        with self.assertRaisesRegex(ValueError, 'exceeds candidate version'): self.compose()

    def test_boot_owner_redirection(self):
        b = json.loads(self.before['boot.json']); b['app_capabilities'][0]['image_source']['path'] = 'other.elf'
        self.before['boot.json'] = json.dumps(b).encode()
        with self.assertRaisesRegex(ValueError, 'source identity'): self.compose()

    def test_internal_install_forbidden(self):
        self.before['ble_buttons.elf'] = b'wrong-placement'
        with self.assertRaisesRegex(ValueError, 'external path'): self.compose()

    def test_grant_count_preserved(self):
        b = json.loads(self.before['boot.json']); b['app_capabilities'][0]['grants'].append({})
        self.before['boot.json'] = json.dumps(b).encode()
        with self.assertRaisesRegex(ValueError, 'grant count'): self.compose()

    def test_missing_mirror(self):
        del self.external[q.MIRROR]
        with self.assertRaisesRegex(ValueError, 'external path'): self.compose()

    def test_mirror_mismatch(self):
        self.external[q.MIRROR] = self.manifest
        with self.assertRaisesRegex(ValueError, 'mirror differs'): self.compose()

    def test_duplicate_owner(self):
        b = json.loads(self.before['boot.json']); b['app_capabilities'] *= 2
        self.before['boot.json'] = json.dumps(b).encode()
        with self.assertRaisesRegex(ValueError, 'source identity'): self.compose()

    def test_paths(self):
        for name in ('../evil', '/absolute', 'a/../b', 'a\\b', 'a//b'):
            with self.subTest(name=name), self.assertRaises(ValueError): q.safe_name(name)

    def test_archive_rejects_duplicate(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / 'a.zip'
            with zipfile.ZipFile(p, 'w') as z:
                z.writestr('a', 'one'); z.writestr('a', 'two')
            with self.assertRaisesRegex(ValueError, 'Duplicate'): q.archive_files(p)

    def test_inventory_detects_change(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td); (p / 'a').write_bytes(b'one'); before = q.inventory(p)
            (p / 'a').write_bytes(b'two'); self.assertNotEqual(q.inventory(p), before)
            (p / 'link').symlink_to('a')
            with self.assertRaisesRegex(ValueError, 'symlink'): q.inventory(p)

    def test_original_gate_unchanged(self):
        for name in ('scripts/package_serial_transfer.py', 'scripts/build_serial_transfer_pair.py',
                     'scripts/serial_transfer_qualification.py', 'docs/serial-transfer-mode/source-pins.json'):
            self.assertEqual((ROOT / name).read_bytes(), q.git(ROOT, 'show', q.BASE + ':' + name))


@unittest.skipUnless(os.environ.get('T039_PRODUCT_ARTIFACT'), 'Transported artifact not supplied')
class TransportControls(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'artifact'
        shutil.copytree(os.environ['T039_PRODUCT_ARTIFACT'], self.root)
        self.source = q.git(ROOT, 'rev-parse', 'HEAD').decode().strip()
        self.digest = os.environ['T039_PRODUCT_RECEIPT_SHA256']

    def verify(self):
        return q.verify(self.root, self.source, self.digest)

    def test_transport_good(self):
        self.assertEqual(self.verify()['status'], 'host-product-admission-qualified')

    def test_transport_wrong_head(self):
        self.source = '0' * 40
        with self.assertRaisesRegex(ValueError, 'source head'): self.verify()

    def test_transport_wrong_receipt(self):
        self.digest = '0' * 64
        with self.assertRaisesRegex(ValueError, 'Receipt digest'): self.verify()

    def test_transport_tampered_elf(self):
        with (self.root / 'candidate/external' / q.ELF).open('ab') as f: f.write(b'x')
        with self.assertRaisesRegex(ValueError, 'artifact changed'): self.verify()

    def test_transport_missing_file(self):
        (self.root / 'candidate/store/boot.json').unlink()
        with self.assertRaisesRegex(ValueError, 'artifact changed'): self.verify()

    def test_transport_extra_file(self):
        (self.root / 'unrecorded').write_text('extra')
        with self.assertRaisesRegex(ValueError, 'artifact changed'): self.verify()


if __name__ == '__main__':
    unittest.main()
