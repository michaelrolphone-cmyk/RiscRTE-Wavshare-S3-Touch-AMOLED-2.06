#!/usr/bin/env python3
"""Run focused native RF/input/status and primitive-raster gates from pinned sources."""
import argparse
import json
from pathlib import Path
import re
import tempfile
from package_crash_sdr import PINS, encoded, require, run, sha

DIMENSIONS = {'native-canvas': [(160,160),(200,200),(240,240),(410,502),(320,240),(640,240),(240,320)],
              'native-raster': [(160,160),(240,240),(410,502),(640,240)]}
COUNTS = {'native-canvas': ('checks',41), 'native-raster': ('comparisons',79)}


def verify_report(label, report):
    expected={(w,h,san) for w,h in DIMENSIONS[label] for san in (False,True)}
    require(report['hardware_verified'] is False, 'Host test must not claim physical hardware qualification')
    rows=report['runs'];actual=[(*row['dimensions'],row['sanitized']) for row in rows]
    require(len(actual)==len(expected) and set(actual)==expected, 'Incomplete/duplicate native matrix: '+label)
    metric,count=COUNTS[label]
    for row in rows:
        require(type(row['sanitized']) is bool and isinstance(row['command'],list) and row['command'], 'Invalid source test receipt')
        values=re.findall(r'(?<![\w-])'+metric+r'=(\d+)(?!\d)',row['result'])
        require(values==[str(count)], 'Incomplete native assertions: '+label)
        if label=='native-raster':require(row['result'].endswith(' PASS'), 'Native raster comparison did not pass')
    return dict(runs=len(rows), assertions_or_comparisons_per_run=count, total=len(rows)*count, passed=True)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('system','utilities','output'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();require(not a.output.exists() or not any(a.output.iterdir()),'Fresh SDR qualification output required')
    a.output.mkdir(parents=True,exist_ok=True);out=a.output.resolve()
    with tempfile.TemporaryDirectory(prefix='sdr-native-pinned-') as td:
        roots={}
        for label,path,key in [('system',a.system,'sdr_system_revision'),('utilities',a.utilities,'sdr_utilities_revision')]:
            require(run('git','-C',path,'rev-parse','HEAD').strip()==PINS[key], 'Wrong focused SDR source: '+label)
            require(not run('git','-C',path,'diff','HEAD','--name-only').strip(), 'Dirty focused SDR source: '+label)
            root=Path(td)/label;run('git','init','-q',root);run('git','-C',root,'fetch','--depth=1',path.resolve(),PINS[key]);run('git','-C',root,'checkout','-q','--detach','FETCH_HEAD')
            roots[label]=root
        import sys
        commands={
            'native-canvas':[sys.executable,roots['utilities']/'scripts/test_rf_native_canvas.py','--system-apps',roots['system'],'--output',out/'native-canvas'],
            'native-raster':[sys.executable,roots['system']/'scripts/test_rf_native_raster.py','--output',out/'native-raster'],
        }
        results={}
        for label,command in commands.items():
            (out/(label+'.log')).write_text(run(*command))
            results[label]=verify_report(label,json.loads((out/label/'evidence.json').read_text()))
        hashes={label:sha((roots[label]/path).read_bytes()) for label,path in [('utilities','scripts/test_rf_native_canvas.py'),('system','scripts/test_rf_native_raster.py')]}
        declared_data=(roots['utilities']/'docs/rf-native-qualification.json').read_bytes()
        declared=json.loads(declared_data)
        require(declared['hardware_verified'] is False and declared['system_source']['published_equivalent']==PINS['sdr_system_revision'], 'Declared SDR qualification source mismatch')
        for label,key in [('utilities','test_source_sha256'),('system','system_test_source_sha256')]:
            for path,digest in declared[key].items():
                require(sha((roots[label]/path).read_bytes())==digest, 'Declared test-source digest differs: '+path)
        (out/'source-reported-qualification.json').write_bytes(declared_data)

    report=dict(sdr_system_revision=PINS['sdr_system_revision'],sdr_utilities_revision=PINS['sdr_utilities_revision'],source_checkouts_isolated=True,source_test_sha256=hashes,source_report_sha256=sha(declared_data),source_report_preserved_without_claiming_full_suite_pass=True,hardware_tested=False,results=results)
    (out/'qualification.json').write_bytes(encoded(report));print(json.dumps(report,indent=2))


if __name__=='__main__':main()
