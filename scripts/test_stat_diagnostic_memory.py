#!/usr/bin/env python3
"""Reject changed target workspace, machine, placement and IQ reservation evidence."""
import copy,json,unittest
from package_stat_diagnostic import DOCS,pins
from stat_diagnostic_memory import compare,measure
class Memory(unittest.TestCase):
 def fixture(self):
  baseline=json.loads((DOCS/'baseline-target-memory.json').read_bytes());c=copy.deepcopy(baseline['linked']);e=pins()['target_workspace_bytes']
  for n,v in e.items():c['workspaces'][n]['bytes']=v
  return c,baseline['linked'],copy.deepcopy(baseline['iq']),baseline['iq'],e
 def test_target_delta_and_gap(self):
  v=compare(*self.fixture());self.assertEqual(v['workspace_deltas'],{'diagnostic_workspace':192,'serial_state':4,'serial_workspace':8});self.assertEqual(v['internal_gap_before_iq'],496)
 def test_target_rejects_host_and_custody_and_placement(self):
  for mutation in ['machine','elf','size','section','bank','heap','iram','reservation','locks']:
   a=list(self.fixture())
   if mutation=='machine':a[0]['machine']='x86_64'
   elif mutation=='elf':a[0]['elf']['sha256']='0'*64
   elif mutation=='size':a[0]['workspaces']['serial_workspace']['bytes']-=1
   elif mutation=='section':a[0]['workspaces']['diagnostic_workspace']['section']='.dram0.bss'
   elif mutation=='bank':a[2]['bank_bytes']-=1
   elif mutation=='heap':a[2]['heap_start']=a[2]['bank_base']+1
   elif mutation=='iram':a[2]['iram_end']=a[2]['iram_alias']+1
   elif mutation=='reservation':a[2]['reservation_table']=[]
   else:a[4].pop('serial_state')
   with self.subTest(mutation=mutation),self.assertRaises(ValueError):compare(*a)
if __name__=='__main__':unittest.main()
