#!/usr/bin/env python3
"""Frozen-contract and exact released-store provisioning negative controls."""
import argparse
import copy
import json
from pathlib import Path
import unittest
import package_provisioning as p

class Contracts(unittest.TestCase):
    def test_frozen_historical_contracts(self):
        pins=p.pins(); self.assertEqual(p.baseline_contract(pins)['version'],pins['baseline_version'])
    def test_canonical_home_receipt(self):
        pins=p.pins(); proof=json.loads((p.DOCS/'common-home.json').read_bytes())
        self.assertTrue(proof['independent_builds_identical'])
        self.assertEqual(proof['default_sha256'],pins['default_sha256'])
        self.assertFalse(proof['hardware_tested'])
    def test_product_profile_is_additive(self):
        profile=(p.ROOT/'profiles/provisioning-native.cmake').read_text()
        self.assertIn('include("${CMAKE_CURRENT_LIST_DIR}/native-idf61.cmake")',profile)
        for name in ('RISC_NATIVE_PACKAGE_VOLUME=1','RISC_NATIVE_PROVISION_REQUEST=1','RISC_PLATFORM_CAPACITY=32'):
            self.assertEqual(profile.count(name),1)
        self.assertNotIn('SERIAL_SD',profile)

class Payloads(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not ARGS.baseline: raise unittest.SkipTest('Exact payload inputs are built separately')
        from read_only_spiffs import read_image
        cls.pins=p.pins();cls.contract=p.baseline_contract(cls.pins)
        factory=ARGS.baseline.read_bytes()
        p.require(p.record(factory)=={'bytes':cls.contract['factory_bytes'],'sha256':cls.contract['factory_sha256']},'Exact factory required')
        cls.before=read_image(factory[0x2f0000:0x840000],0x550000)
        p.check_baseline(cls.before,cls.contract)
        cls.default=(ARGS.home/'default.elf').read_bytes();cls.manifest=(ARGS.home/'default.json').read_bytes()
        cls.providers={}
        for folder,name,catalog in ((ARGS.catalog,'installed-apps',True),(ARGS.internal,'pkg-internal',False)):
            elf,manifest=p.provider_inputs(folder,cls.pins,catalog)
            cls.providers.update({name+'/driver.elf':elf,name+'/manifest.json':manifest})
        cls.revision='a'*40;cls.firmware=b'RISC_RUNTIME_VERSION:0.4.7\0'
        cls.after,cls.mirrors=p.compose(cls.before,cls.default,cls.manifest,cls.providers,cls.pins,cls.revision,cls.firmware)
    def verify(self,files):
        return p.verify_store(self.before,files,self.default,self.manifest,self.providers,self.pins,self.revision,self.firmware)
    def test_complete_composition(self):
        proof=self.verify(self.after);self.assertEqual(proof['file_count'],132);self.assertEqual(proof['elf_count'],64)
        self.assertEqual(proof['unchanged_elf_count'],61)
    def test_every_retained_payload_is_protected(self):
        for n in set(self.before)-set(p.CHANGED):
            changed=dict(self.after);changed[n]+=b'x'
            with self.subTest(path=n),self.assertRaises(ValueError):self.verify(changed)
    def test_missing_or_extra_file(self):
        for n in self.after:
            changed=dict(self.after);del changed[n]
            with self.subTest(path=n),self.assertRaises(ValueError):self.verify(changed)
        with self.assertRaises(ValueError):self.verify(dict(self.after,extra=b'x'))
    def test_all_added_provider_payloads_protected(self):
        for n in p.ADDED:
            changed=dict(self.after);changed[n]+=b'x'
            with self.subTest(path=n),self.assertRaises(ValueError):self.verify(changed)
    def test_resigned_provider_replacement_is_rejected(self):
        for n in p.ADDED:
            changed=dict(self.after);changed[n]+=b'x'
            providers=dict(self.providers);providers[n]=changed[n]
            with self.subTest(path=n),self.assertRaises(ValueError):
                p.verify_store(self.before,changed,self.default,self.manifest,providers,self.pins,self.revision,self.firmware)
    def test_baseline_cannot_be_resigned(self):
        before=dict(self.before);before['wifi_settings.elf']+=b'x'
        changed=dict(self.after);changed['wifi_settings.elf']=before['wifi_settings.elf']
        with self.assertRaises(ValueError):
            p.verify_store(before,changed,self.default,self.manifest,self.providers,self.pins,self.revision,self.firmware)
    def test_only_home_policy_gains_authority(self):
        before=json.loads(self.before['boot.json']);after=json.loads(self.after['boot.json'])
        retained=copy.deepcopy(after['drivers'][:36])
        usb=next(d for d in retained if d['manifest']=='usb-msc/manifest.json')
        self.assertEqual(usb.pop('bindings'),[p.grant('storage.volume',12)])
        self.assertEqual(retained,before['drivers'])
        for old,new in zip(before['app_capabilities'],after['app_capabilities']):
            if old['manifest']=='default.json':
                self.assertEqual(new['grants'],old['grants']+[p.grant('software.installed-apps'),p.grant('storage.key-value',6),p.grant('storage.volume',12)])
            else:self.assertEqual(old,new)
        self.assertEqual([r for r in after['app_capabilities'] if r.get('image_source')],[r for r in before['app_capabilities'] if r.get('image_source')])
        self.assertFalse(any(r.get('image_source') for r in after['drivers']))
        self.assertEqual(self.mirrors['mirror_count'],0)
    def test_private_serial_is_not_application_destination(self):
        boot=json.loads(self.after['boot.json']);self.assertEqual(boot['installation']['volume_instance'],12)
        self.assertEqual(boot['installation']['internal_volume_instance'],0)
        self.assertEqual(boot['installation']['namespace_range'],{'first':3000,'count':128})
    def test_unrelated_policy_mutation_rejected(self):
        boot=json.loads(self.after['boot.json']);boot['app_capabilities'][0]['grants'].append(p.grant('storage.files',2))
        changed=dict(self.after,**{'boot.json':p.encoded(boot)})
        with self.assertRaises(ValueError):self.verify(changed)
    def test_settings_and_springboard_retained(self):
        for n in ('settings.elf','settings.json','springboard.elf','springboard.json'):
            self.assertEqual(self.before[n],self.after[n])
    def test_factory_authority_delta_is_explicit(self):
        old=json.loads(self.before['boot.json']);new=json.loads(self.after['boot.json']);g=p.grant('storage.key-value',6)
        home=lambda b:next(r for r in b['app_capabilities'] if r['manifest']=='default.json')
        self.assertNotIn(g,home(old)['grants']);self.assertIn(g,home(new)['grants'])
        self.assertTrue(any(r['manifest']!='default.json' and g in r['grants'] for r in old['app_capabilities']))
        self.assertNotIn('cohort_migration',new)

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    for n in ('baseline','home','catalog','internal'):parser.add_argument('--'+n,type=Path)
    ARGS,remaining=parser.parse_known_args()
    if any(vars(ARGS).values()) and not all(vars(ARGS).values()):parser.error('All exact payload inputs must be supplied together')
    unittest.main(argv=[__file__,*remaining])
