#!/usr/bin/env python3
"""Focused fail-closed tests; synthetic mutations are never product payloads."""
import copy
import hashlib
import io
import json
import unittest
import subprocess
import sys
import zipfile
import warnings
import audit_catalog_payload as a

C = json.loads(a.CONTRACT.read_bytes())

class PayloadTests(unittest.TestCase):
    def test_complete_declared_inventory(self):
        p = a.payload_inputs(C, 'create', 'sensitive')
        self.assertEqual(p['totals'], {'bytes': 138235, 'file_count': 3})
        self.assertEqual([x['destination'] for x in p['files']],
                         ['/' + n for n in sorted(C['companion']['files'])])
        self.assertEqual(p['bindings'][0]['namespace_id'], '12')
        self.assertNotIn('method_id', p)

    def test_exact_paths_work_with_either_selected_naming_mode(self):
        sensitive = a.payload_inputs(C, 'create', 'sensitive')
        folded = a.payload_inputs(C, 'create', 'ascii-insensitive')
        self.assertEqual(sensitive['files'], folded['files'])
        self.assertEqual(sensitive['directories'], folded['directories'])
        self.assertNotEqual(sensitive['inventory_sha256'], folded['inventory_sha256'])
        self.assertEqual(folded['volumes'][0]['requirements']['case_semantics'], 'ascii-insensitive')

    def test_naming_semantics_must_be_explicit(self):
        for mode in (None, '', 'fatfs', 'unknown'):
            with self.subTest(mode=mode), self.assertRaises(ValueError):
                a.payload_inputs(C, 'create', mode)
        with self.assertRaises(TypeError): a.payload_inputs(C, 'create')

    def test_digest_is_canonical(self):
        p = a.payload_inputs(C, 'create', 'sensitive'); digest = p.pop('inventory_sha256')
        self.assertEqual(hashlib.sha256(a.encoded(p)).hexdigest(), digest)

    def test_each_operation_is_explicit(self):
        for mode in ('create', 'replace'):
            with self.subTest(mode=mode):
                p = a.payload_inputs(C, mode, 'sensitive')
                self.assertEqual({x['operation'] for x in p['files']}, {mode})
                self.assertEqual([x['previous'] for x in p['files']], [None] * 3)
                self.assertEqual(p['volumes'][0]['requirements']['operations'][-1], mode)

    def test_reject_implicit_operations(self):
        for mode in ('upsert', 'copy-tree', 'delete', '', None):
            with self.subTest(mode=mode), self.assertRaises(ValueError):
                a.payload_inputs(C, mode, 'sensitive')

    def test_exact_parent_closure(self):
        p = a.payload_inputs(C, 'create', 'sensitive')
        self.assertEqual([x['path'] for x in p['directories']], ['/Apps', '/Apps/lora_messages'])
        self.assertTrue(all(x['operation'] == 'ensure-directory' for x in p['directories']))

    def test_internal_policy_selected(self):
        boot = {'app_capabilities': copy.deepcopy(C['external_app_policies']), 'drivers': []}
        self.assertEqual(a.check_external_sources(boot, C), C['external_app_policies'])

    def test_omitted_external_policy_rejected(self):
        with self.assertRaises(ValueError):
            a.check_external_sources({'app_capabilities': [], 'drivers': []}, C)

    def test_private_scratch_is_not_app_destination(self):
        boot = {'app_capabilities': copy.deepcopy(C['external_app_policies']), 'drivers': []}
        boot['app_capabilities'][0]['image_source']['volume_instance'] = 2
        with self.assertRaises(ValueError): a.check_external_sources(boot, C)

    def test_extra_external_app_rejected(self):
        boot = {'app_capabilities': copy.deepcopy(C['external_app_policies']) * 2, 'drivers': []}
        with self.assertRaises(ValueError): a.check_external_sources(boot, C)

    def test_external_storage_dependency_rejected(self):
        boot = {'app_capabilities': C['external_app_policies'], 'drivers': [{'image_source': {}}]}
        with self.assertRaises(ValueError): a.check_external_sources(boot, C)

    def test_byte_corruption_rejected(self):
        with self.assertRaises(ValueError): a.exact(b'bad', a.record(b'good'), 'test')

    def test_source_repository_required(self):
        with self.assertRaises(ValueError): a.source_bytes(C, {})

    def test_schema_cannot_allow_empty_inventory(self):
        s = {'properties': {'payload': {'properties': {
            'volumes': {'minItems': 1}, 'files': {'minItems': 1},
            'totals': {'properties': {'file_count': {'minimum': 1}}}}}}}
        a.verify_schema(s)
        for key in ('volumes', 'files'):
            broken = copy.deepcopy(s); broken['properties']['payload']['properties'][key]['minItems'] = 0
            with self.subTest(key=key), self.assertRaises(ValueError): a.verify_schema(broken)

    def test_recorded_external_elf_qualification_matches_exact_inputs(self):
        q=json.loads((a.CONTRACT.parent / 'external-elf/qualification.json').read_bytes())
        self.assertEqual(q['runtime_commit'], C['runtime_revision'])
        self.assertEqual(q['lora_elf_sha256'], C['companion']['files'][a.ELF]['sha256'])
        self.assertEqual(q['required_capability_count'], len(C['internal_lora_manifest']['requires']))
        self.assertEqual(q['delivered_lora_policy'], C['external_app_policies'][0])
        self.assertEqual({x['sanitized'] for x in q['tests']}, {False, True})
        self.assertTrue(all(x['missing_import_rejections']==11 and
                            x['production_removable_image_snapshots']==2 for x in q['tests']))
        self.assertFalse(q['target_instructions_executed'])
        self.assertFalse(q['hardware_tested'])

    def test_external_qualification_rejects_optimization(self):
        p=subprocess.run([sys.executable, '-O', str(a.ROOT / 'scripts/qualify_external_lora.py')],
                         capture_output=True, text=True)
        self.assertNotEqual(p.returncode, 0)
        self.assertIn('Python optimization disables qualification assertions', p.stderr)

    def synthetic_companion(self, mutate=None, extra=None):
        c = copy.deepcopy(C); internal = c['internal_lora_manifest']
        external = {**internal, 'version': '0.1.17'}
        files = {a.ELF: b'SYNTHETIC TEST ONLY', 'Apps/lora_messages/manifest.json': a.encoded(external)}
        files['suite-card.json'] = a.encoded({'apps': [{'image': a.ELF,
            'manifest': 'Apps/lora_messages/manifest.json', 'sha256': a.record(files[a.ELF])['sha256']}]})
        if mutate: mutate(files)
        c['companion']['files'] = {n: a.record(b) for n,b in files.items()}
        archive = io.BytesIO()
        with warnings.catch_warnings():
            warnings.simplefilter('ignore', UserWarning)
            with zipfile.ZipFile(archive, 'w') as z:
                for n,b in files.items(): z.writestr(n,b)
                if extra: z.writestr(extra, b'not declared')
        release = {'source_revision': c['companion']['source_revision'],
            'release_tag': c['companion']['release_tag'],
            'elf_sha256': c['companion']['files'][a.ELF]['sha256'],
            'qualification': {'files': c['companion']['files']}}
        assets = {'Waveshare-LoRa-0.1.17-SD-card.zip': archive.getvalue(), 'release.json': a.encoded(release)}
        c['companion']['assets'] = {n:a.record(b) for n,b in assets.items()}
        return c, assets, {'lora_messages.json': a.encoded(internal)}

    def test_metadata_matches_internal_authority(self):
        self.assertEqual(len(a.companion_files(*self.synthetic_companion())), 3)

    def test_manifest_cannot_grant_new_authority(self):
        def mutate(files):
            m=json.loads(files['Apps/lora_messages/manifest.json']); m['requires'].append({'api':1,'capability':'new.authority'})
            files['Apps/lora_messages/manifest.json']=a.encoded(m)
        with self.assertRaises(ValueError): a.companion_files(*self.synthetic_companion(mutate))

    def test_companion_index_cannot_misdirect(self):
        def mutate(files): files['suite-card.json']=a.encoded({'apps':[]})
        with self.assertRaises(ValueError): a.companion_files(*self.synthetic_companion(mutate))

    def test_extra_unrelated_archive_member_rejected(self):
        with self.assertRaises(ValueError): a.companion_files(*self.synthetic_companion(extra='unrelated.txt'))

    def test_duplicate_archive_member_rejected(self):
        with self.assertRaises(ValueError): a.companion_files(*self.synthetic_companion(extra=a.ELF))

    def test_companion_bytes_mutation_rejected(self):
        c, assets, files = self.synthetic_companion(); assets['release.json'] += b'\n'
        with self.assertRaises(ValueError): a.companion_files(c, assets, files)

    def test_missing_asset_rejected(self):
        c, assets, files = self.synthetic_companion(); del assets['release.json']
        with self.assertRaises(ValueError): a.companion_files(c, assets, files)

if __name__ == '__main__': unittest.main()
