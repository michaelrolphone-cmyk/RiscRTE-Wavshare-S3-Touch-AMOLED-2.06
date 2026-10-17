#!/usr/bin/env python3
"""Static per-file plan guards; no catalog or device operations."""
import copy
import unittest
from build_minimal_sd_pair import PAIR_MODES,payload_entries
from package_minimal_sd import record
from publish_minimal_sd_release import pair_asset_names

class Plans(unittest.TestCase):
    def setUp(self):
        self.files={f'Apps/example{i}/example.elf':bytes([i])*32 for i in range(45)}
        self.previous={name:record(data) for name,data in list(self.files.items())[:3]}
    def test_all_three_explicit_plans(self):
        for mode in PAIR_MODES:
            rows=payload_entries(self.files,mode,self.previous)
            self.assertEqual(len(rows),45)
            self.assertEqual(sum(r['operation']=='replace' for r in rows),{'create':0,'replace':45,'known-lora':3}[mode])
            for row in rows:
                name=row['destination'].removeprefix('/')
                self.assertEqual(row['previous'],self.previous[name] if mode=='known-lora' and name in self.previous else None)
                self.assertEqual({k:row[k] for k in ('bytes','sha256')},record(self.files[name]))
    def test_historical_hash_and_bytes_required(self):
        for field,value in [('sha256','0'*64),('bytes',31)]:
            history=copy.deepcopy(self.previous);history[next(iter(history))][field]=value
            with self.assertRaises(ValueError):payload_entries(self.files,'known-lora',history)
    def test_missing_historical_target_rejected(self):
        files=dict(self.files);del files[next(iter(self.previous))]
        with self.assertRaises(ValueError):payload_entries(files,'known-lora',self.previous)
    def test_unknown_or_automatic_mode_rejected(self):
        for mode in ['upsert','automatic','mixed','']:
            with self.assertRaises(ValueError):payload_entries(self.files,mode,self.previous)
    def test_canonical_extension_is_exact(self):
        names=pair_asset_names('0.1.57');self.assertEqual(len(names),14)
        self.assertIn('Waveshare-0.1.57-SD-Apps-known-lora.zip',names)
        self.assertEqual(sum(n.endswith('.zip') for n in names),3)

if __name__=='__main__':unittest.main()
