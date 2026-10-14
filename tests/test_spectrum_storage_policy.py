import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from spectrum_storage_policy import provision
class SpectrumPolicy(unittest.TestCase):
 def test_explicit_bounded_namespaces_and_idempotence(self):
  m={'id':'audio_spectrum','requires':[{'capability':'contexts.service','api':1}]}
  p={'manifest':'audio_spectrum.json','grants':[{'capability':'storage.app-data','api':1,'instance_id':2}]}
  a,b=provision(m,p)
  self.assertEqual([g['instance_id'] for g in b['grants'] if g['capability']=='storage.shared-data'],[2,3,4])
  self.assertEqual(provision(a,b),(a,b));self.assertEqual(len(p['grants']),1);self.assertEqual(len(m['requires']),1)
  other={**m,'id':'calculator'};self.assertEqual(provision(other,p),(other,p))
if __name__=='__main__':unittest.main()
