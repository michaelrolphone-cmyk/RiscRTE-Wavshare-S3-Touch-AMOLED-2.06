#!/usr/bin/env python3
"""The fixed boot-test recipe must use its pinned Runtime manifest schema."""
import argparse
from pathlib import Path
import re
import sys
import unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import build_boot_test as recipe
parser=argparse.ArgumentParser()
parser.add_argument('--runtime',type=Path,required=True)
args,rest=parser.parse_known_args()
class HistoricalManifest(unittest.TestCase):
 def test_exact_runtime_pin_and_manifest(self):
  self.assertEqual(recipe.PINS['runtime'],'56036e51b34e2054600d4465554a101914dec7a4')
  manifest=recipe.legacy_diagnostic_manifest()
  self.assertEqual(manifest['id'],'watch-bringup')
  self.assertNotIn('launcher_visible',manifest)
  source=(args.runtime/'src/bootstrap/Runtime.cpp').read_text()
  match=re.search(r'keys\(manifest,\{([^}]+)\},\{([^}]+)\}\)',source)
  self.assertIsNotNone(match)
  allowed=set(re.findall(r'"([^"\n]+)"',match[1]+match[2]))
  self.assertNotIn('launcher_visible',allowed)
  self.assertLessEqual(set(manifest),allowed)
  self.assertFalse(set({**manifest,'launcher_visible':False})<=allowed)
if __name__=='__main__': unittest.main(argv=[sys.argv[0],*rest])
