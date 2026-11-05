#!/usr/bin/env python3
"""Exercise evaluated external profile and compiler-visible policy rejection."""
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
import shared_wifi_native as policy
ROOT=Path(__file__).resolve().parents[1]

class PolicyTests(unittest.TestCase):
    def test_profile_preserves_parent(self):
        with tempfile.TemporaryDirectory() as tmp:
            before,after=policy.profile_delta(ROOT,Path(tmp),'profiles/shared-home-capacity.cmake',shutil.which('cmake'))
            self.assertEqual(len(after['definitions'].split(';')),len(before['definitions'].split(';'))+2)
            self.assertIn('RISC_ENABLE_RADIO_IQ=1',after['definitions'])
            self.assertIn('RISC_ENABLE_SDMMC=1',after['definitions'])
            self.assertIn('RISC_NATIVE_SERIAL_TRANSFER_MODE=1',after['definitions'])

    def test_profile_refuses_other_changes(self):
        changes=[
            ('RISC_NATIVE_SETTINGS_LOCAL_ONLY=0','RISC_NATIVE_SETTINGS_LOCAL_ONLY=1'),
            ('RISC_NATIVE_SETTINGS_LOCAL_FRESH=0','RISC_NATIVE_SETTINGS_LOCAL_FRESH=1'),
            ('RISC_NATIVE_SETTINGS_LOCAL_ONLY=0','RISC_NATIVE_SETTINGS_LOCAL_ONLY=0 RISC_NATIVE_SETTINGS_LOCAL_ONLY=0'),
            ('RISC_NATIVE_SETTINGS_LOCAL_FRESH=0','RISC_NATIVE_SETTINGS_LOCAL_FRESH=0 RISC_ENABLE_SDMMC=0')]
        for old,new in changes:
            with self.subTest(change=new),tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp);shutil.copytree(ROOT/'profiles',root/'profiles')
                path=root/'profiles/shared-wifi-native.cmake';path.write_text(path.read_text().replace(old,new))
                with self.assertRaises(ValueError):
                    policy.profile_delta(root,root,'profiles/shared-home-capacity.cmake',shutil.which('cmake'))

    def test_actual_header_macros(self):
        header=(ROOT/'profiles/native-idf61-settings.h').read_text()
        command=['c++','-E','-dM','-x','c++','-DRISC_NATIVE_SETTINGS_LOCAL_ONLY=0',
            '-DRISC_NATIVE_SETTINGS_LOCAL_FRESH=0','-include',str(ROOT/'profiles/native-idf61-settings.h'),'-']
        output=subprocess.check_output(command,input='',text=True)
        macros=policy.checked_macros(output,header)
        self.assertEqual(macros['RISC_NATIVE_SETTINGS_VOLUME_INSTANCE'],'12')
        for key in macros:
            with self.subTest(key=key):
                bad=output.replace('#define '+key+' '+macros[key],'#define '+key+' unexpected')
                with self.assertRaises(ValueError): policy.checked_macros(bad,header)

    def test_preprocess_preserves_flags(self):
        row={'arguments':['g++','-include','policy.h','-DKEEP=1','-Iinclude','-o','Backend.o','-c','Backend.cpp','-MMD','-MF','Backend.d']}
        self.assertEqual(policy.preprocess_command(row),
            ['g++','-include','policy.h','-DKEEP=1','-Iinclude','Backend.cpp','-E','-dM'])
        with self.assertRaises(ValueError): policy.preprocess_command({'arguments':['g++','-o']})

    def test_pins_and_read_only_workflow(self):
        pins=json.loads((ROOT/'docs/shared-wifi-native/source-pins.json').read_text())
        self.assertFalse(pins['publication_enabled'])
        self.assertEqual(pins['runtime_revision'],'532c502fb2aad358d46166d5fd1df8358148f20e')
        self.assertEqual(pins['sdk_revision'],'fff9895c82d744c7237be8847347bdd1b07c6643')
        self.assertEqual(pins['settings_header_git_blob'],'1a1cea41e216827a8ff17e6860a3abcab981c6a9')
        workflow=(ROOT/'.github/workflows/shared-wifi-native.yml').read_text()
        self.assertIn('contents: read',workflow)
        self.assertNotIn('contents: write',workflow)
        self.assertNotIn('publish',workflow)

if __name__=='__main__': unittest.main()
