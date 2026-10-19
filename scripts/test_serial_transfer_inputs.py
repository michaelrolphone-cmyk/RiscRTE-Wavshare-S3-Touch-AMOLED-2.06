#!/usr/bin/env python3
"""Production successor-input command and actual compile-selection controls."""
import importlib.util
from pathlib import Path
import tempfile
spec=importlib.util.spec_from_file_location('transfer_inputs',Path(__file__).with_name('build_serial_transfer_inputs.py'));m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
def reject(call):
    try:call()
    except ValueError:return
    raise AssertionError('Invalid input accepted')
p=Path('/fixture');cmd=m.home_command(p/'watch',p/'system',p/'utilities',p/'compiler',p/'out')
assert cmd.count('--serial-transfer-mode')==1 and cmd[cmd.index('--role')+1]=='default' and '--automatic-provision' in cmd
runtime=p/'runtime';good={'file':str(runtime/'src/main.cpp'),'directory':'/','arguments':['c++','-DRISC_NATIVE_SERIAL_TRANSFER_MODE=1']}
assert m.runtime_selection([good],runtime)==[str(runtime/'src/main.cpp')]
for flags in ([],['-DRISC_NATIVE_SERIAL_TRANSFER_MODE=0'],['-DRISC_NATIVE_SERIAL_TRANSFER_MODE=1']*2):reject(lambda:m.runtime_selection([dict(good,arguments=flags)],runtime))
reject(lambda:m.runtime_selection([],runtime))
old=b'a/provisioning-index/0.1.63/b';new=b'a/provisioning-index/0.1.64/b';m.catalog_delta(old,new)
for value in (old,new+b'extra',new.replace(b'a/',b'z/')):reject(lambda:m.catalog_delta(old,value))
print('Transfer successor input selection PASS: Home explicit flag/default role; actual Runtime compile flag; exact URL-only catalog delta; missing/off/ambiguous selection refused')

if __name__=='__main__':
    import argparse,hashlib,json
    parser=argparse.ArgumentParser()
    for name in ('selected','feature-off','historical-feature-off','previous-selected','receipt'):parser.add_argument('--'+name,type=Path)
    args=parser.parse_args()
    if args.selected:
        assert all((args.feature_off,args.historical_feature_off,args.previous_selected,args.receipt))
        m.require_home(args.selected)
        reject(lambda:m.require_home(args.feature_off))
        reject(lambda:m.require_home(args.previous_selected))
        for name in ('default.elf','default.json','clock.elf','clock.json'):
            assert (args.feature_off/name).read_bytes()==(args.historical_feature_off/name).read_bytes(),name
        assert json.loads((args.feature_off/'default.json').read_text())['version']=='0.20.3'
        assert json.loads((args.selected/'default.json').read_text())['version']=='0.20.4'
        files={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for folder in (args.selected,args.feature_off,args.historical_feature_off,args.previous_selected) for p in folder.iterdir() if p.name in ('default.elf','default.json','clock.elf','clock.json','build.json')}
        files[str(Path(__file__))]=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
        files[str(Path(m.__file__))]=hashlib.sha256(Path(m.__file__).read_bytes()).hexdigest()
        result=dict(passed=True,selected_home=True,old_selected_version_refused=True,feature_off_refused=True,feature_off_artifacts_identical=True,source_and_artifact_sha256=files,limits='Actual selected and feature-off Home target artifacts; actual Runtime compile selection tested with compiler-command controls, not a full SDK Runtime build.')
        args.receipt.write_text(json.dumps(result,indent=2)+'\n');print('Actual selected-version/feature-off artifact controls PASS')
