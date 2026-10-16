#!/usr/bin/env python3
"""Exercise exact baseline/candidate plans in both banks; never access a device."""
import argparse,json,sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
for key in ('runtime','baseline','candidate','output'):p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args();sys.path.insert(0,str(a.runtime.resolve()/'scripts'))
from prepare_preserving_update import plan,layout,pair,record,selection,ota,sha
baseline=a.baseline.read_bytes();candidate=a.candidate.read_bytes();digest=sha(baseline)
assert digest=='93531640691a0a1b3b6718e01aeca388fe3cbe6c5e4f9f396ff262d0c166fa35'
geometry=layout(baseline);assert geometry==layout(candidate)
expanded,native,stores,size=geometry;_,firmware,store=pair(baseline,0,geometry)
new=pair(candidate,0,geometry);assert new[1]==firmware and new[2]!=store
results=[]
def active(image):return (max(ota(image[0xff0000+i*4096:0xff0020+i*4096])[0] for i in range(2) if ota(image[0xff0000+i*4096:0xff0020+i*4096]))-1)%2
for source in (0,1):
 snapshot=bytearray(baseline);snapshot[0x9000:0xf000]=bytes((i*17+3)%256 for i in range(0x6000));snapshot[0x270000:0x2f0000]=bytes((i*23+7)%256 for i in range(0x80000))
 if source:
  snapshot[native[1]:native[1]+len(firmware)]=firmware;snapshot[stores[1]:stores[1]+size]=store;snapshot[0xff3000:0xff3060]=record(1,firmware,store,True,expanded);snapshot[0xff1000:0xff2000]=selection(2,2)
 writes,receipt=plan(snapshot,baseline,candidate,digest);staged=bytearray(snapshot)
 for _,offset,data in writes[:-1]:
  end=offset+(len(data)+4095)//4096*4096;staged[offset:end]=b'\xff'*(end-offset);staged[offset:offset+len(data)]=data;assert active(staged)==source
 for start,end in receipt['preserved_ranges']:assert staged[start:end]==snapshot[start:end]
 _,offset,data=writes[-1]
 for cut in range(33):
  interrupted=bytearray(staged);interrupted[offset:offset+4096]=b'\xff'*4096;interrupted[offset:offset+cut]=data[:cut];assert active(interrupted)==(1-source if cut==32 else source)
 staged[offset:offset+4096]=data;assert active(staged)==1-source and pair(staged,1-source,geometry)[1:]==new[1:]
 for start,end in receipt['preserved_ranges']:assert staged[start:end]==snapshot[start:end]
 for corrupt_offset in (0,0x8000,0x10000,0x2f0000,0xff2000):
  corrupt=bytearray(candidate);corrupt[corrupt_offset]^=1
  try:plan(snapshot,baseline,corrupt,digest)
  except ValueError:pass
  else:raise AssertionError('Corrupt candidate accepted')
 results.append({'active_bank':source,'target_bank':1-source,'selection_cuts':33,'preserved_ranges':True,'candidate_integrity':True,'corrupt_inputs_rejected':True})
report={'baseline_sha256':digest,'candidate_sha256':sha(candidate),'actual_candidate':True,'software_fixture':True,'hardware_tested':False,'device_accessed':False,'results':results}
a.output.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
