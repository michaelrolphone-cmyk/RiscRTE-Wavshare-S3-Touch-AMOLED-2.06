#!/usr/bin/env python3
"""Negative gates for exact official-native reuse; software fixtures only."""
import copy
import json
from pathlib import Path
import tempfile
import warnings
import zipfile
import stage_sdr_baseline_native as m

original=copy.deepcopy(m.PINS)
passed=0

def reject(call):
    global passed
    try:
        call()
    except (ValueError, KeyError, zipfile.BadZipFile):
        passed+=1
        return
    raise AssertionError('Invalid native custody accepted')

with tempfile.TemporaryDirectory(prefix='native-reuse-gates-') as td:
    root=Path(td);archive=root/'official.zip'
    firmware=b'firmware fixture';elf=b'ELF fixture';baseline=bytearray(b'\xff'*0x1000000)
    baseline[0x10000:0x10000+len(firmware)]=firmware;baseline=bytes(baseline)
    metadata=dict(source_revision='1'*40,runtime_revision='2'*40,version='0.1.45')
    m.PINS.update(baseline_product='1'*40,runtime_revision='2'*40,baseline_version='0.1.45',
                  baseline_sha256=m.sha(baseline),baseline_native_sha256=m.sha(firmware),baseline_native_elf_sha256=m.sha(elf))
    payloads={'firmware.bin':firmware,'firmware.elf':elf,'release.json':json.dumps(metadata).encode()}
    def make(values,duplicate=False):
        with warnings.catch_warnings(),zipfile.ZipFile(archive,'w') as out:
            warnings.simplefilter('ignore',UserWarning)
            for name,data in values.items():out.writestr(name,data)
            if duplicate:out.writestr('firmware.bin',firmware)
        m.PINS['baseline_evidence_sha256']=m.sha(archive.read_bytes())
    make(payloads)
    files,receipt=m.verified_native(baseline,archive)
    assert files=={'firmware.bin':firmware,'firmware.elf':elf,'partitions.bin':baseline[0x8000:0x9000]}
    assert receipt['native_reused_unchanged'] and receipt['baseline_product']=='1'*40
    reject(lambda:m.verified_native(baseline[:-1],archive))
    old=m.PINS['baseline_evidence_sha256'];m.PINS['baseline_evidence_sha256']='0'*64
    reject(lambda:m.verified_native(baseline,archive));m.PINS['baseline_evidence_sha256']=old
    for key,value in [('source_revision','3'*40),('runtime_revision','3'*40),('version','0.1.44')]:
        altered=dict(metadata,**{key:value});make(dict(payloads,**{'release.json':json.dumps(altered).encode()}))
        reject(lambda:m.verified_native(baseline,archive))
    for name in ('firmware.bin','firmware.elf'):
        make(dict(payloads,**{name:b'changed'}));reject(lambda:m.verified_native(baseline,archive))
    make(payloads,duplicate=True);reject(lambda:m.verified_native(baseline,archive))
    make(payloads);different=bytearray(baseline);different[0x10000]^=1;different=bytes(different)
    m.PINS['baseline_sha256']=m.sha(different);reject(lambda:m.verified_native(different,archive))

m.PINS.clear();m.PINS.update(original)
print(json.dumps(dict(passed=True,negative_cases=passed,native_reuse_identity_verified=True)))
