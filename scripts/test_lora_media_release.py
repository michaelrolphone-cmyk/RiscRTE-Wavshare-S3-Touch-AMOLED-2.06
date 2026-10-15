#!/usr/bin/env python3
"""Fail-closed package, version, policy and separate-release regression checks."""
import copy
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile
import package_lora_media as p

class MediaRelease(unittest.TestCase):
    def setUp(self):
        self.old = b'old-elf'
        self.new = b'new-elf'
        self.pins = dict(p.PINS, prior_elf_sha256=p.sha(self.old), prior_elf_bytes=len(self.old),
                         elf_sha256=p.sha(self.new), elf_bytes=len(self.new))
        self.patch = patch.object(p, 'PINS', self.pins); self.patch.start(); self.addCleanup(self.patch.stop)
        self.before = {p.ELF:self.old, p.MANIFEST:(p.DOCS/'firmware-lora-manifest.json').read_bytes(),
            'suite-card.json':(json.dumps({'apps':[{'image':p.ELF,'manifest':p.MANIFEST,'sha256':p.sha(self.old)}],
              'discovery':'explicit internal boot policy; catalog entry comes from admitted lora_messages.json',
              'schema':'riscrte.provisioned-card-content','schema_version':1},separators=(',',':'))+'\n').encode()}

    def test_exact_overlay(self):
        before=copy.deepcopy(self.before); after=p.overlay(self.before,self.new)
        self.assertEqual(self.before,before);self.assertEqual(set(after),p.MEMBERS)
        self.assertEqual(after[p.ELF],self.new)
        self.assertEqual(after[p.MANIFEST].replace(b'0.1.17',b'0.1.16'),before[p.MANIFEST])
        expected=json.loads(before['suite-card.json']);expected['apps'][0]['sha256']=p.sha(self.new)
        self.assertEqual(json.loads(after['suite-card.json']),expected)

    def test_missing_member_rejected(self):
        del self.before['suite-card.json']
        with self.assertRaises(ValueError):p.overlay(self.before,self.new)

    def test_extra_member_rejected(self):
        self.before['firmware.bin']=b'forbidden'
        with self.assertRaises(ValueError):p.overlay(self.before,self.new)

    def test_wrong_predecessor_rejected(self):
        self.before[p.ELF]+=b'wrong'
        with self.assertRaises(ValueError):p.overlay(self.before,self.new)

    def test_wrong_repair_rejected(self):
        with self.assertRaises(ValueError):p.overlay(self.before,self.new+b'wrong')

    def test_manifest_authority_change_rejected(self):
        row=json.loads(self.before[p.MANIFEST]);row['requires'].append({'capability':'radio.lora','api':2})
        self.before[p.MANIFEST]=json.dumps(row).encode()
        with self.assertRaises(ValueError):p.overlay(self.before,self.new)

    def test_prior_version_change_rejected(self):
        self.before[p.MANIFEST]=self.before[p.MANIFEST].replace(b'0.1.16',b'0.1.15')
        with self.assertRaises(ValueError):p.overlay(self.before,self.new)

    def test_content_path_change_rejected(self):
        row=json.loads(self.before['suite-card.json']);row['apps'][0]['image']='Apps/other.elf'
        self.before['suite-card.json']=json.dumps(row).encode()
        with self.assertRaises(ValueError):p.overlay(self.before,self.new)

    def test_content_digest_change_rejected(self):
        row=json.loads(self.before['suite-card.json']);row['apps'][0]['sha256']='0'*64
        self.before['suite-card.json']=json.dumps(row).encode()
        with self.assertRaises(ValueError):p.overlay(self.before,self.new)

    def test_baseline_archive_digest_rejected(self):
        with self.assertRaises(ValueError):p.read_baseline(b'not-the-official-card')

    def test_archive_reproducible_complete_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as td:
            a,b=Path(td)/'a.zip',Path(td)/'b.zip';p.archive(a,self.before);p.archive(b,self.before)
            self.assertEqual(a.read_bytes(),b.read_bytes())
            with zipfile.ZipFile(a) as z:self.assertEqual(set(z.namelist()),p.MEMBERS)
            with self.assertRaises(FileExistsError):p.archive(a,self.before)

    def test_exact_release_contract(self):
        pins=json.loads((p.DOCS/'source-pins.json').read_bytes())
        self.assertEqual((pins['release_tag'],pins['app_version'],pins['firmware_version']),('test-lora-media-0.1.17','0.1.17','0.1.45'))
        self.assertEqual(p.sha((p.DOCS/'upstream-cohort.json').read_bytes()),pins['upstream_cohort_sha256'])
        policy=json.loads((p.DOCS/'firmware-lora-policy.json').read_bytes())
        self.assertEqual(policy['image_source'],{'path':p.ELF,'volume_instance':12})
        self.assertFalse(any(r['capability']=='radio.lora' for r in policy['grants']))
        workflow=(p.ROOT/'.github/workflows/lora-media-release.yml').read_text()
        self.assertNotIn('factory-erases',workflow);self.assertNotIn('pio run',workflow)
        self.assertIn('contents: write',workflow);self.assertIn('--latest=false',workflow)
        self.assertIn('refusing overwrite',workflow)

if __name__=='__main__':unittest.main()
