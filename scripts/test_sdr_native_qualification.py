#!/usr/bin/env python3
"""Reject incomplete or inflated focused SDR qualification claims."""
import copy,json
from qualify_sdr_native_sources import COUNTS,DIMENSIONS,verify_report
passed=0
for label,sizes in DIMENSIONS.items():
 metric,count=COUNTS[label]
 good={'hardware_verified':False,'runs':[dict(dimensions=[w,h],sanitized=san,command=['cc'],result=f'{metric}={count} PASS')for w,h in sizes for san in (False,True)]}
 assert verify_report(label,good)['passed']
 variants=[]
 bad=copy.deepcopy(good);bad['hardware_verified']=True;variants.append(bad)
 bad=copy.deepcopy(good);bad['runs'].pop();variants.append(bad)
 bad=copy.deepcopy(good);bad['runs'][0]=bad['runs'][1];variants.append(bad)
 bad=copy.deepcopy(good);bad['runs'][0]['result']=f'{metric}={count-1} PASS';variants.append(bad)
 bad=copy.deepcopy(good);bad['runs'][0]['command']=[];variants.append(bad)
 for bad in variants:
  try:verify_report(label,bad)
  except ValueError:passed+=1
  else:raise AssertionError('Invalid report accepted')
print(json.dumps(dict(passed=True,negative_cases=passed)))
