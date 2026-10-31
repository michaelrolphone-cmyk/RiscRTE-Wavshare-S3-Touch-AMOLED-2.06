#!/usr/bin/env python3
"""Small orchestration/negative tests; does not substitute for a native build."""
import argparse
import copy
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
parser = argparse.ArgumentParser()
parser.add_argument('--baseline-scripts', type=Path)
args, remaining = parser.parse_known_args()
if args.baseline_scripts: sys.path.insert(0, str(args.baseline_scripts))
sys.path.insert(0, str(ROOT / 'scripts'))
import build_shared_app_native as b

class Builder(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.root = Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)
        self.pin = b.pins()
        self.elf = b'fixture-elf'; self.manifest = json.dumps({'version':'0.23.2'}).encode()
        self.pin['home'] = {'elf':b.record(self.elf), 'manifest':b.record(self.manifest), 'version':'0.23.2'}
        self.sources = {'watch': self.root / 'watch'}
        self.build = {'verified_dependencies': {r:{'commit':self.pin[r+'_revision']} for r in ('system','utilities')},
                      'compiler_sha256':'c', 'serial_transfer_mode':True, 'automatic_provision':True,
                      'artifacts':{'default':{'defines':['-DWATCH_SERIAL_TRANSFER_MODE']}}}
        self.a = SimpleNamespace(first=self.root/'a',second=self.root/'b',compiler=self.root/'gcc')
        for folder in (self.a.first,self.a.second):
            folder.mkdir(); (folder/'build.json').write_text(json.dumps(self.build))
        self.verifier = SimpleNamespace(verify=lambda *a: {'passed':True},
            check_build=lambda *a:(self.elf,self.manifest,self.build))
        self.loader = SimpleNamespace(exec_module=lambda module:None)
        self.spec = SimpleNamespace(loader=self.loader)
        self.patches = [patch.object(b.importlib.util,'spec_from_file_location',return_value=self.spec),
                        patch.object(b.importlib.util,'module_from_spec',return_value=self.verifier),
                        patch.object(b.controlled,'compiler_family',return_value={'s3-gcc':{'sha256':'c'}})]
        for p in self.patches: p.start(); self.addCleanup(p.stop)
    def canonical(self): return b.canonical(self.a,self.sources,self.pin)
    def test_joint_home(self): self.assertEqual(self.canonical()[:2],(self.elf,self.manifest))
    def test_system_pin(self):
        self.build['verified_dependencies']['system']['commit']='bad'
        with self.assertRaisesRegex(ValueError,'dependency'):self.canonical()
    def test_utilities_pin(self):
        self.build['verified_dependencies']['utilities']['commit']='bad'
        with self.assertRaisesRegex(ValueError,'dependency'):self.canonical()
    def test_compiler(self):
        self.build['compiler_sha256']='bad'
        with self.assertRaisesRegex(ValueError,'compiler'):self.canonical()
    def test_elf_hash(self):
        self.pin['home']['elf']['sha256']='bad'
        with self.assertRaisesRegex(ValueError,'bytes'):self.canonical()
    def test_manifest_hash(self):
        self.pin['home']['manifest']['sha256']='bad'
        with self.assertRaisesRegex(ValueError,'bytes'):self.canonical()
    def test_home_version(self):
        self.pin['home']['version']='0.20.4'
        with self.assertRaisesRegex(ValueError,'version'):self.canonical()
    def edit_second(self,key,value):
        row=copy.deepcopy(self.build);row[key]=value
        (self.a.second/'build.json').write_text(json.dumps(row))
    def test_second_missing_provision(self):
        self.edit_second('automatic_provision',False)
        with self.assertRaisesRegex(ValueError,'Joint'):self.canonical()
    def test_second_missing_transfer(self):
        self.edit_second('serial_transfer_mode',False)
        with self.assertRaisesRegex(ValueError,'Joint'):self.canonical()
    def test_ambiguous_flag(self):
        self.edit_second('artifacts',{'default':{'defines':['-DWATCH_SERIAL_TRANSFER_MODE']*2}})
        with self.assertRaisesRegex(ValueError,'ambiguous'):self.canonical()
    def test_retained_profile_guard(self):
        with patch.object(b,'DOCS',self.root):
            p=copy.deepcopy(self.pin);p['profile']='profiles/native-idf61.cmake'
            (self.root/'source-pins.json').write_text(json.dumps(p))
            with self.assertRaisesRegex(ValueError,'transfer profile'):b.pins()
    def test_actual_transfer_flags(self):
        from build_serial_transfer_inputs import runtime_selection
        runtime=self.root/'runtime';source=runtime/'src/Runtime.cpp'
        row={'file':str(source),'directory':str(self.root),'arguments':['cc','-DRISC_NATIVE_SERIAL_TRANSFER_MODE=1']}
        self.assertEqual(runtime_selection([row],runtime),[str(source)])
        row['arguments'].append('-DRISC_NATIVE_SERIAL_TRANSFER_MODE=0')
        with self.assertRaisesRegex(ValueError,'ambiguous'):runtime_selection([row],runtime)
    def test_actual_provisioning_flags(self):
        runtime=self.root/'runtime';source=runtime/'src/Runtime.cpp'
        row={'file':str(source),'directory':str(self.root),'arguments':['cc','-DRISC_NATIVE_PACKAGE_VOLUME=1','-DRISC_NATIVE_PROVISION_REQUEST=1','-DRISC_PLATFORM_CAPACITY=32']}
        self.assertEqual(len(b.retained.provisioning_compile_selection([row],runtime)[1]),1)
        row['arguments'].pop()
        with self.assertRaisesRegex(ValueError,'flags'):b.retained.provisioning_compile_selection([row],runtime)
    def test_layout_existing_output(self):
        with self.assertRaisesRegex(ValueError,'nonexistent'):
            b.controlled.validate_layout({'product':ROOT},self.root/'build',self.root,ROOT)
    def test_compile_before_qualification(self):
        # Keep the public same-process ordering visible, not a detached proof CLI.
        import inspect
        text=inspect.getsource(b.main)
        self.assertLess(text.index('subprocess.run(command'),text.index('collect_build_proof'))
        self.assertLess(text.index('collect_build_proof'),text.index('native.freeze'))
        self.assertLess(text.index('native.freeze'),text.index('qualify(args'))
        self.assertNotIn('build-proof',text)
    def test_original_companion_bytes(self):
        import inspect
        text=inspect.getsource(b.qualify)
        self.assertIn("'sd-apps.zip': args.companion.read_bytes()",text)
        self.assertNotIn('make_archive(payload)',text)
        self.assertLess(text.index('package.companion_files'),text.index("'sd-apps.zip'"))
    def test_no_feed_emission(self):
        import inspect
        text=inspect.getsource(b.qualify)
        self.assertNotIn('serial_transfer_feed',text)
        self.assertIn('feed_emitted=False',text)
        self.assertIn('factory-candidate-erases-data',text)

if __name__=='__main__':unittest.main(argv=[sys.argv[0],*remaining])
