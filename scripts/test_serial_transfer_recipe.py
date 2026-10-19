"""Production recipe source/pin dispatch controls, without running a native build."""
import ast,hashlib,importlib,json,unittest
from pathlib import Path
import package_serial_transfer as package
ROOT=package.ROOT
class Recipe(unittest.TestCase):
 def test_selected_helpers_use_current_exact_pins(self):
  pins=package.pins(final=True)
  for name in ('qualify_serial_transfer_legacy','qualify_serial_transfer_logs'):
   module=importlib.import_module(name);self.assertEqual(module.pins(final=True),pins)
  self.assertEqual(pins['serial_transfer']['runtime_version'],'0.4.17')
  self.assertEqual(pins['version'],'0.1.64')
 def test_selected_profile_includes_unchanged_base(self):
  profile=(ROOT/'profiles/serial-transfer-native.cmake').read_text()
  self.assertEqual(profile.count('RISC_NATIVE_SERIAL_TRANSFER_MODE=1'),1)
  self.assertIn('include("${CMAKE_CURRENT_LIST_DIR}/provisioning-native.cmake")',profile)
  for path in ('profiles/native-idf61.cmake','profiles/provisioning-native.cmake'):
   self.assertEqual(hashlib.sha256((ROOT/path).read_bytes()).hexdigest(),package.pins()['historical_contracts'][path])
 def test_actual_native_compile_selection_is_required(self):
  text=(ROOT/'scripts/build_serial_transfer_native.py').read_text()
  self.assertIn("'profiles/serial-transfer-native.cmake'",text)
  self.assertIn("runtime_selection(json.loads((args.native_build / 'compile_commands.json').read_bytes()), sources['runtime'])",text)
  self.assertIn('require_home(args.first); require_home(args.second)',text)
  self.assertIn("transfer_mode['compiled_runtime_rows'] = len(transfer_rows)",text)
  self.assertIn('validate_transfer(q[\'transfer_mode\'], p[\'runtime_revision\'])',(ROOT/'scripts/serial_transfer_release.py').read_text())
 def test_workflow_runs_new_producer_and_source_checks(self):
  script=(ROOT/'scripts/run_serial_transfer_native_ci.sh').read_text();workflow=(ROOT/'.github/workflows/serial-transfer-native.yml').read_text()
  self.assertIn('build_serial_transfer_inputs.py',script);self.assertIn('--selected-inputs "$NATIVE_ROOT/transfer-inputs"',script)
  self.assertIn('test_home_transfer_exit.py',script);self.assertIn('scripts/run_serial_transfer_native_ci.sh',workflow)
  self.assertIn('release/sd-apps-0.1.64',workflow);self.assertNotIn('release/sd-apps-0.1.63',workflow)
if __name__=='__main__':unittest.main()
