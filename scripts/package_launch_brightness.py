#!/usr/bin/env python3
"""Build and qualify shared launch brightness over the exact official 0.1.47 store."""
import argparse, hashlib, io, json, os, re, subprocess, sys, tempfile, zipfile
from pathlib import Path
import package_crash_sdr as baseline_tools
import package_native_faces as predecessor_tools
from package_crash_sdr import require, sha, encoded, git_bytes, checksums, archive, verify_trace_storage
ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / 'docs/launch-brightness'
PINS = json.loads((DOCS / 'source-pins.json').read_text())
PREFIX = 'Waveshare-0.1.48-Launch-Brightness'
FACTORY = PREFIX + '-factory-erases-data-0x0.bin'
RUNTIME_HELPERS = baseline_tools.RUNTIME_HELPERS
APPS = json.loads((DOCS / 'app-cohort.json').read_text())
EXPECTED_APPS = set('alarms app_store audio_spectrum battery ble_buttons ble_scanner ble_touchpad calculator countdown file_browser frequency_generator ota_update points_in_time stopwatch timecard waterfall wifi_settings'.split())
PRODUCT_INPUTS = predecessor_tools.PRODUCT_INPUTS + (
    'scripts/package_launch_brightness.py', 'scripts/test_launch_brightness_release.py',
    'scripts/qualify_launch_brightness.py', 'scripts/stage_launch_baseline_native.py',
    'docs/launch-brightness/source-pins.json', 'docs/launch-brightness/app-cohort.json',
    'docs/launch-brightness/RELEASE-NOTES.txt', 'docs/launch-brightness/RELEASE-ROUTE.txt',
    'docs/launch-brightness/PRESERVING-UPDATE.txt', 'docs/launch-brightness/prepare.py',
    'docs/launch-brightness/verify_readbacks.py', '.github/workflows/launch-brightness-release.yml',
    'scripts/package_launch_brightness_media.py', 'scripts/test_launch_brightness_media.py',
    *('docs/launch-brightness-media/' + name for name in ('README.md','INSTALL.txt','RELEASE-NOTES.txt','source-pins.json','upstream-cohort.json','firmware-lora-policy.json','firmware-lora-manifest.json')),
)

def run(*args, **kwargs):
    kwargs['env'] = {**os.environ, **kwargs.get('env', {}), 'PYTHONDONTWRITEBYTECODE': '1'}
    return baseline_tools.run(*args, **kwargs)

def verify_final_pins():
    require(PINS['finalized'] is True and type(PINS['publication_enabled']) is bool, 'Final pins and explicit publication gate required')
    require((PINS['version'], PINS['baseline_version'], PINS['release_tag']) == ('0.1.48','0.1.47','test-launch-brightness-0.1.48'), 'Release identity mismatch')
    require(PINS['baseline_tag']=='test-native-faces-0.1.47', 'Baseline tag differs')
    require(PINS['system_revision'] == '24270c36cd4bc1edb7bb2e8d860501eaa5105d43' and PINS['adapter_revision'] == '96742a20af660808cae6cd3a36eadd12a83a460f', 'Exact qualified producer and adapter required')
    require(PINS['runtime_revision'] == baseline_tools.PINS['runtime_revision'] and PINS['native_changed'] is False, 'Native Runtime must remain unchanged')
    for key in ('baseline_product','system_revision','adapter_revision','baseline_system_revision','springboard_revision','bridge_revision','utilities_revision','image_helper_revision','vendor_revision'):
        require(re.fullmatch('[0-9a-f]{40}', PINS[key]), 'Immutable revision missing: '+key)
    for key in ('baseline_sha256','baseline_evidence_sha256','baseline_home_sha256','baseline_native_sha256','baseline_native_elf_sha256','compiler_sha256','replay_driver_sha256','app_cohort_sha256'):
        require(re.fullmatch('[0-9a-f]{64}', PINS[key]), 'Digest missing: '+key)
    require(set(APPS) == EXPECTED_APPS and len(APPS) == 17, 'Complete qualified 17-app set required')
    require(PINS['changed_apps'] == sorted(APPS), 'Changed app set differs')
    require(PINS['changed_store_files'] == sorted(['cohort.json']+[name+suffix for name in APPS for suffix in ('.elf','.json')]), 'Changed store allowlist differs')
    require(sha((DOCS/'app-cohort.json').read_bytes()) == PINS['app_cohort_sha256'], 'App cohort digest differs')
    for name,row in APPS.items():
        require(re.fullmatch('[0-9a-f]{64}',row['sha256']) and re.fullmatch('[0-9a-f]{64}',row['deployed_sha256']) and row['sha256'] != row['deployed_sha256'], 'Changed app identity required: '+name)
        old = tuple(map(int,row['old_version'].split('.')))
        require(len(old)==3 and row['proposed_version']=='.'.join(map(str,(*old[:2],old[2]+1))), 'Exact manifest successor required: '+name)
    require(PINS['baseline_home_sha256'] == '56a42bb1b47dc6b243db55cd224f04bd50907eac3f99d3510df34d2c8aa75e65', 'Preserved native Home required')

def verify_baseline_bytes(data):
    require(len(data)==0x1000000 and sha(data)==PINS['baseline_sha256'], 'Exact released .47 factory required')

def replace_apps(before, replacements):
    require(set(replacements)==set(APPS), 'Complete 17-app replacement required')
    result=dict(before)
    for name,row in APPS.items():
        old,new=before[name+'.elf'],replacements[name]
        require(sha(old)==row['deployed_sha256'] and new!=old, 'Baseline app mismatch: '+name)
        require(sha(new)==row['sha256'] and len(new)==row['bytes'], 'Replayed app mismatch: '+name)
        require(new[:7]==b'\x7fELF\x01\x01\x01' and new[16:20]==b'\x03\x00\x5e\x00', 'Expected ELF32 Xtensa ET_DYN app')
        manifest=json.loads(before[name+'.json'])
        require(manifest['version']==row['old_version'], 'Baseline app version differs: '+name)
        result[name+'.elf']=new
        result[name+'.json']=(json.dumps(dict(manifest,version=row['proposed_version']),separators=(',',':'))+'\n').encode()
    return result

def verify_changed_store(before, store):
    require(set(before)==set(store), 'Store inventory changed')
    changed=sorted(name for name in before if before[name]!=store[name])
    require(changed==PINS['changed_store_files'], 'Unexpected store changes: '+str(changed))
    require(sum(n.endswith('.elf') for n in store)==62, 'Complete 62-ELF baseline required')
    for name,row in APPS.items():
        require(sha(store[name+'.elf'])==row['sha256'], 'App digest differs: '+name)
        require(json.loads(store[name+'.json'])==dict(json.loads(before[name+'.json']),version=row['proposed_version']), 'App manifest authority changed: '+name)
    for name,key in (('default.elf','baseline_home_sha256'),('springboard.elf','baseline_springboard_sha256'),('springboard.json','baseline_springboard_manifest_sha256')):
        require(sha(store[name])==PINS[key], 'Preserved payload differs: '+name)
    return changed

def replay_apps(system, compiler, output, source_cache=None):
    require(run('git','-C',system,'rev-parse','HEAD').strip()==PINS['system_revision'], 'Producer HEAD differs')
    require(not run('git','-C',system,'diff','HEAD','--name-only').strip(), 'Producer source is dirty')
    driver=system/'scripts/replay_shared_crash_apps.py';spec=system/'docs/shared-app-crashes/replay'
    require(sha(driver.read_bytes())==PINS['replay_driver_sha256'] and sha(compiler.read_bytes())==PINS['compiler_sha256'], 'Replay driver/compiler differs')
    require({p.name:sha(p.read_bytes()) for p in spec.iterdir() if p.is_file()}==PINS['replay_spec_sha256'], 'Replay spec closure differs')
    recipes=json.loads((spec/'wave.json').read_bytes())
    require(set(recipes)==set(APPS), 'Replay inventory differs')
    command=[sys.executable,driver,'--product','wave','--compiler',compiler,'--output',output]
    if source_cache:command.extend(['--source-cache',source_cache.resolve()])
    run(*command)
    report=json.loads((output/'receipt.json').read_bytes())
    require(report['product']=='wave' and report['source_inputs_verified'] is True and set(report['apps'])==set(APPS), 'Incomplete strict replay')
    require(report['driver_sha256']==PINS['replay_driver_sha256'] and report['spec_sha256']==PINS['replay_spec_sha256'] and report['compiler_sha256']==PINS['compiler_sha256'], 'Replay source identity differs')
    require(report['repositories']==json.loads((spec/'inputs.json').read_bytes())['repositories'], 'Replay source revisions differ')
    binaries={};evidence={'receipt.json':encoded(report)}
    for name,row in report['apps'].items():
        data=(output/(name+'.elf')).read_bytes();expected=APPS[name];recipe=recipes[name]
        require(sha(data)==row['sha256']==expected['sha256']==recipe['sha256'] and len(data)==row['bytes']==expected['bytes']==recipe['bytes'], 'Strict target identity differs: '+name)
        require(row['symbols']==expected['symbols']==recipe['symbols'], 'Target symbol contract differs: '+name)
        attempts=row['link_attempts'];require(1<=len(attempts)<=6, 'Unbounded linker retry')
        for index,attempt in enumerate(attempts):
            log=Path(attempt['log']);content=log.read_bytes()
            require(sha(content)==attempt['log_sha256'], 'Link log digest differs')
            require(attempt['returncode']==0 and attempt['recognized_linker_abort'] is False if index==len(attempts)-1 else attempt['returncode']!=0 and attempt['recognized_linker_abort'] is True, 'Invalid linker retry history')
            evidence['logs/'+name+'/'+log.name]=content
        binaries[name]=data
    for path in output.rglob('*'):
        relative=path.relative_to(output)
        if path.is_file() and relative.parts[0] not in ('work','sources','debug') and path.suffix in ('.log','.json'):
            evidence['logs/'+relative.as_posix()]=path.read_bytes()
    return binaries,report,evidence


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('baseline', 'evidence', 'runtime', 'system', 'compiler', 'image-helper', 'vendor', 'utilities', 'baseline-system', 'springboard-system', 'bridges', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--source-revision', required=True)
    parser.add_argument('--source-cache', type=Path)
    args = parser.parse_args()
    require(__debug__, 'Do not run with Python -O')
    verify_final_pins()
    product_source_hashes = baseline_tools.verify_product_source(ROOT, args.source_revision, PRODUCT_INPUTS)
    require(not args.output.exists() or not any(args.output.iterdir()), 'Output must be empty')
    runtime, image_helper = args.runtime.resolve(), args.image_helper.resolve()
    native_dir = runtime / '.pio/build/waveshare-t051'
    require(native_dir == runtime / '.pio/build/waveshare-t051', 'Native output must be selected waveshare-t051 build')
    source_hashes = baseline_tools.verify_sources(runtime, image_helper, args.vendor.resolve())
    source_hashes.update({'product/' + name: digest for name, digest in product_source_hashes.items()})
    sys.path[:0] = [str(runtime / 'scripts'), str(image_helper / 'scripts')]
    from prepare_preserving_update import layout, pair, plan, record, selection, ota
    from spiffs_image import read_image
    from paired_bank_images import initial_bank_state
    from paired_candidate import native_proof
    from radio_iq_proof import prove
    from release_assets import esp_image, elf
    import current_bootfs

    baseline = args.baseline.read_bytes()
    verify_baseline_bytes(baseline)
    geometry = layout(baseline)
    require(geometry[0] and geometry[3] == 0x550000, 'ABI3 expanded geometry required')
    _, old_native, old_store = pair(baseline, 0, geometry)
    before = read_image(old_store, geometry[3])
    original = json.loads(before['cohort.json'])
    require(original['version'] == '0.1.47' and original['source_revision'] == PINS['baseline_product'], 'Baseline cohort identity mismatch')
    require(sha(before['springboard.elf']) == PINS['baseline_springboard_sha256'], 'Baseline native-vector Springboard mismatch')
    from stage_launch_baseline_native import verified_native
    native, native_custody = verified_native(baseline, args.evidence)
    require(all((native_dir / name).read_bytes() == native[name] for name in ('firmware.bin','firmware.elf','partitions.bin')), 'Admission native files differ from official baseline')
    firmware = native['firmware.bin']
    require(0 < len(firmware) <= 0x260000, 'Bounded native firmware required')
    require((firmware != old_native) == PINS['native_changed'], 'Native changed status differs from finalized pins')
    require(sha(old_native) == PINS['baseline_native_sha256'], 'Baseline native hash mismatch')
    esp_image(firmware)
    elf(native['firmware.elf'])
    baseline_tools.verify_native_identity(native)
    require(sha(native['firmware.elf']) == PINS['baseline_native_elf_sha256'], 'Official .47 native ELF changed')
    # Regenerate image from this exact ELF, proving ELF/BIN correspondence.
    with tempfile.TemporaryDirectory(prefix='catalog-native-proof-') as td:
        regenerated = Path(td) / 'firmware.bin'
        run(sys.executable, '-m', 'esptool', '--chip', 'esp32s3', 'elf2image', '--flash_mode', 'dio', '--flash_freq', '80m', '--flash_size', '16MB', '-o', regenerated, native_dir / 'firmware.elf')
        require(regenerated.read_bytes() == firmware, 'Native BIN does not match supplied ELF')
    version = re.findall(rb'RISC_RUNTIME_VERSION:([^\x00]+)', firmware)
    require(len(version) == 1, 'Ambiguous Runtime version')
    proof = native_proof(native['firmware.elf'])
    proof['performance_trace'] = verify_trace_storage(native['firmware.elf'])
    proof['radio_iq'] = prove(native['firmware.elf'], target_identity='esp32s3-16mb-waveshare-expanded')
    proof['performance_trace']['static_bytes_before_iq_bank'] = proof['radio_iq']['bank_base'] - proof['radio_iq']['heap_start']
    # Do not replace shipped bootloader or partition table on a native update.
    require(native['partitions.bin'] == baseline[0x8000:0x8000 + len(native['partitions.bin'])], 'Native partition layout differs from installed .47')
    require(native_custody == dict(baseline_product=PINS['baseline_product'], runtime_revision=PINS['runtime_revision'], baseline_factory_sha256=PINS['baseline_sha256'], baseline_evidence_sha256=PINS['baseline_evidence_sha256'], native_sha256=sha(firmware), native_elf_sha256=sha(native['firmware.elf']), native_reused_unchanged=True), 'Native custody receipt differs')
    proof['official_baseline_custody'] = native_custody
    proof.update(native_source_product_revision=baseline_tools.PINS['baseline_product'], native_reused_unchanged=True, baseline_evidence_sha256=PINS['baseline_evidence_sha256'], runtime_revision=PINS['runtime_revision'], bin_sha256=sha(firmware), elf_sha256=sha(native['firmware.elf']), elf_bin_identical=True, source_hashes=source_hashes)
    with tempfile.TemporaryDirectory(prefix='launch-brightness-replay-') as td:
        replacements,target_proof,replay_files=replay_apps(args.system.resolve(),args.compiler.resolve(),Path(td)/'target',args.source_cache)
    springboard=before['springboard.elf']
    store=replace_apps(before,replacements)
    cohort = dict(original, version=PINS['version'], source_revision=args.source_revision, runtime_version=version[0].decode(), firmware_size=len(firmware), firmware_sha256=sha(firmware))
    store['cohort.json'] = (json.dumps(cohort, separators=(',', ':')) + '\n').encode()
    changed_store = verify_changed_store(before, store)
    packed, packing = current_bootfs.build(store, size=geometry[3])
    require(read_image(packed, geometry[3]) == store, 'Packed store round-trip differs')
    candidate = bytearray(baseline)
    candidate[0x10000:0x270000] = b'\xff' * 0x260000
    candidate[0x10000:0x10000 + len(firmware)] = firmware
    candidate[0x2f0000:0x840000] = packed
    state = initial_bank_state(firmware, packed, True, True)
    candidate[0xff2000:0xff2000 + len(state)] = state
    candidate = bytes(candidate)
    require(layout(candidate) == geometry and pair(candidate, 0, geometry)[1:] == (firmware, packed), 'Candidate bank binding failed')
    for start, end in ((0, 0x2f0000), (0x840000, 0xff2000), (0xff3000, 0x1000000)):
        require(candidate[start:end] == baseline[start:end], 'Bytes outside store/state changed')
    with tempfile.TemporaryDirectory(prefix='launch-brightness-source-') as td:
        qualified=Path(td)/'results'
        run(sys.executable,ROOT/'scripts/qualify_launch_brightness.py','--system',args.system.resolve(),'--runtime',runtime,'--utilities',args.utilities.resolve(),'--baseline-system',args.baseline_system.resolve(),'--springboard-system',args.springboard_system.resolve(),'--bridges',args.bridges.resolve(),'--output',qualified)
        source_qualification=json.loads((qualified/'qualification.json').read_bytes())
        require(source_qualification['passed'] is True, 'Source qualification failed')
        qualification_files={p.relative_to(qualified).as_posix():p.read_bytes() for p in qualified.rglob('*') if p.is_file() and p.suffix in ('.json','.log')}
    helpers = {name: (runtime / 'scripts' / name).read_bytes() for name in RUNTIME_HELPERS}
    require(all(data == git_bytes(runtime, PINS['runtime_revision'], 'scripts/' + name) for name, data in helpers.items()), 'Preserving helper source mismatch')
    metadata = dict(PINS, source_revision=args.source_revision, candidate_sha256=sha(candidate), native_sha256=sha(firmware), native_elf_sha256=sha(native['firmware.elf']), hardware_tested=False, device_accessed=False, verified_hardware_fix=False, system_unchanged=False, native_changed=PINS['native_changed'], all_other_store_payloads_unchanged=True, springboard_sha256=sha(springboard), springboard_manifest_sha256=sha(store['springboard.json']), home_elf_sha256=sha(store['default.elf']), retained_wake_policy_added=False, springboard_unchanged=True, replayed_app_count=17, changed_app_count=17, unchanged_elf_count=45, includes_t023_provisioning=False, factory_erases_saved_data=True, sd_unchanged=True)
    metadata['artifact_sources']={'native':{'runtime_revision':PINS['runtime_revision'],'product_revision':baseline_tools.PINS['baseline_product'],'official_evidence_sha256':PINS['baseline_evidence_sha256'],'reused_byte_identically':True},'home':{'preserved_from_product':PINS['baseline_product'],'sha256':sha(store['default.elf'])},'replayed_apps':{name:{'producer_revision':PINS['system_revision'],'recipe':'docs/shared-app-crashes/replay/wave.json:'+name,'sha256':row['sha256']} for name,row in APPS.items()}}
    metadata['external_media_companion_required']=True
    results = []
    def active(image):
        return (max(ota(image[0xff0000 + i * 4096:0xff0020 + i * 4096])[0] for i in range(2) if ota(image[0xff0000 + i * 4096:0xff0020 + i * 4096])) - 1) % 2
    for source in (0, 1):
        snapshot = bytearray(baseline)
        snapshot[0x9000:0xf000] = bytes((i * 17 + 3) % 256 for i in range(0x6000))
        snapshot[0x270000:0x2f0000] = bytes((i * 23 + 7) % 256 for i in range(0x80000))
        if source:
            snapshot[geometry[1][1]:geometry[1][1] + len(old_native)] = old_native
            snapshot[geometry[2][1]:geometry[2][1] + geometry[3]] = old_store
            snapshot[0xff3000:0xff3060] = record(1, old_native, old_store, True, True)
            snapshot[0xff1000:0xff2000] = selection(2, 2)
        writes, receipt = plan(snapshot, baseline, candidate, PINS['baseline_sha256'])
        staged = bytearray(snapshot)
        for _, offset, data in writes[:-1]:
            end = offset + (len(data) + 4095) // 4096 * 4096
            staged[offset:end] = b'\xff' * (end - offset)
            staged[offset:offset + len(data)] = data
            require(active(staged) == source, 'Active selection changed before final write')
        for start, end in receipt['preserved_ranges']:
            require(staged[start:end] == snapshot[start:end], 'Protected range changed')
        _, offset, data = writes[-1]
        for cut in range(33):
            interrupted = bytearray(staged)
            interrupted[offset:offset + 4096] = b'\xff' * 4096
            interrupted[offset:offset + cut] = data[:cut]
            require(active(interrupted) == (1 - source if cut == 32 else source), 'Interrupted selection failed')
        staged[offset:offset + len(data)] = data
        require(active(staged) == 1 - source and pair(staged, 1 - source, geometry)[1:] == (firmware, packed), 'Final native/store pair mismatch')
        for corrupt_offset in (0, 0x8000, 0x10000, 0x2f0000, 0xff2000):
            corrupt = bytearray(candidate); corrupt[corrupt_offset] ^= 1
            try:
                plan(snapshot, baseline, corrupt, PINS['baseline_sha256'])
            except ValueError:
                pass
            else:
                raise ValueError('Corrupted candidate accepted')
        for start, end in receipt['preserved_ranges']:
            require(staged[start:end] == snapshot[start:end], 'Final selection changed protected range')
        rejected = 0
        for corruption in ('bootloader', 'active-native', 'active-store', 'active-state', 'unconfirmed', 'equal-sequence'):
            invalid = bytearray(snapshot)
            if corruption == 'unconfirmed':
                selected_sector = 0xff1000 if source else 0xff0000
                invalid[selected_sector:selected_sector + 4096] = selection(source + 1, 0)
            elif corruption == 'equal-sequence':
                invalid[0xff0000:0xff1000] = selection(2, 2)
                invalid[0xff1000:0xff2000] = selection(2, 2)
            else:
                at = {'bootloader': 0, 'active-native': geometry[1][source], 'active-store': geometry[2][source], 'active-state': 0xff2000 + source * 4096}[corruption]
                invalid[at] ^= 1
            try:
                plan(invalid, baseline, candidate, PINS['baseline_sha256'])
            except ValueError:
                rejected += 1
            else:
                raise ValueError('Invalid snapshot accepted: ' + corruption)
        results.append(dict(active_bank=source, target_bank=1-source, selection_cuts=33, protected_ranges_unchanged=True, corrupt_inputs_rejected=True, invalid_snapshots_rejected=rejected))
    with tempfile.TemporaryDirectory(prefix='native-ui-admission-') as td:
        temporary = Path(td)
        for label, files in (('baseline', before), ('candidate', store)):
            for name, data in files.items():
                path = temporary / label / name; path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(data)
        run(sys.executable, ROOT / 'scripts/verify_native_faces_admission.py', '--runtime', runtime, '--watch', image_helper, '--baseline-store', temporary / 'baseline', '--store', temporary / 'candidate', '--output', temporary / 'admission')
        admission = json.loads((temporary / 'admission/admission.json').read_text())
        require(admission['result']['prepared'] and admission['result']['cohort_validated'] and admission['result']['elf_count'] == 62, 'Full 62-ELF source-bound admission failed')
        require(admission['result']['hardware_calls'] == 0 and admission['result']['storage_calls'] == 0, 'Admission invoked native I/O')
        require(admission['result']['native_elf_sha256'] == sha(native['firmware.elf']), 'Admission used different native ELF')
        run(sys.executable, ROOT / 'scripts/verify_native_faces_admission.py', '--runtime', runtime, '--watch', image_helper, '--baseline-store', temporary / 'baseline', '--store', temporary / 'candidate', '--output', temporary / 'admission-sanitized', env={**os.environ, 'SANITIZE': '1', 'ASAN_OPTIONS': 'detect_leaks=0'})
        sanitized = json.loads((temporary / 'admission-sanitized/admission.json').read_text())
        sanitized['sanitizers'] = ['address', 'undefined']
        sanitized['leak_detection'] = False
        sanitized['leak_detection_note'] = 'LeakSanitizer is incompatible with the executor ptrace sandbox; ASan and UBSan remain enabled.'
        require(sanitized['result'] == admission['result'], 'Sanitized admission result differs')
        kit = dict(helpers, **{'baseline.bin': baseline, 'candidate.bin': candidate, 'release.json': encoded(metadata), 'prepare.py': (DOCS / 'prepare.py').read_bytes(), 'verify_readbacks.py': (DOCS / 'verify_readbacks.py').read_bytes(), 'README.txt': (DOCS / 'PRESERVING-UPDATE.txt').read_bytes(), 'decode_display_perf.py': (ROOT / 'scripts/decode_display_perf.py').read_bytes(), 'DISPLAY-TIMING.md': (ROOT / 'docs/NATIVE_DISPLAY_TIMING.md').read_bytes()})
        kit_dir = temporary / 'kit'; kit_dir.mkdir()
        for name, data in kit.items():
            (kit_dir / name).write_bytes(data)
        run(sys.executable, kit_dir / 'prepare.py', '--snapshot', kit_dir / 'baseline.bin', '--output', temporary / 'plan')
        for flags in ([], ['--selection']):
            run(sys.executable, kit_dir / 'verify_readbacks.py', '--plan', temporary / 'plan/plan.json', '--readbacks', temporary / 'plan', *flags)

    report = dict(metadata, packing=packing, changed_store_files=changed_store, target_proof=target_proof, source_qualification=source_qualification, store_file_count=len(store), native_proof=proof, preserving_banks=results, kit_prepare_and_simulated_readbacks=True)
    notes = (DOCS / 'RELEASE-NOTES.txt').read_text()
    evidence = {'release.json': encoded(metadata), 'assembly-report.json': encoded(report), 'admission.json': encoded(admission), 'admission-sanitized.json': encoded(sanitized), 'native-proof.json': encoded(proof), 'target-proof.json': encoded(target_proof), 'springboard.elf': springboard, 'springboard.json': store['springboard.json'], 'store-SHA256SUMS.txt': checksums(store), 'firmware.elf': native['firmware.elf'], 'firmware.bin': firmware}
    for name in PRODUCT_INPUTS:
        evidence['product-sources/' + name] = (ROOT / name).read_bytes()
    evidence['source-pins.json'] = encoded(PINS)
    for name, data in qualification_files.items():
        evidence['qualification/' + name] = data
    for name, data in replay_files.items():
        evidence['app-replay/' + name] = data
    for name in changed_store:
        evidence['changed-store/' + name] = store[name]
    evidence['runtime-source-diff.patch'] = subprocess.check_output(['git', '-C', str(runtime), 'diff', PINS['runtime_revision'], PINS['runtime_revision']])
    for name in ('src/diagnostics/Performance.h', 'test/run_native_iq_worker_test.sh', 'test/native_iq_worker_test.cpp', 'docs/PERFORMANCE_TRACE.md'):
        path = runtime / name
        if path.is_file():
            evidence['runtime-sources/' + name] = path.read_bytes()
    for name, data in helpers.items():
        evidence['runtime-sources/' + name] = data
    require(product_source_hashes == baseline_tools.verify_product_source(ROOT, args.source_revision, PRODUCT_INPUTS), 'Product sources changed during qualification')
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / FACTORY).write_bytes(candidate)
    (args.output / 'release.json').write_bytes(encoded(metadata))
    (args.output / 'RELEASE-NOTES.txt').write_text(notes)
    (args.output / 'decode_display_perf.py').write_bytes((ROOT / 'scripts/decode_display_perf.py').read_bytes())
    (args.output / 'DISPLAY-TIMING.md').write_bytes((ROOT / 'docs/NATIVE_DISPLAY_TIMING.md').read_bytes())
    archive(args.output / (PREFIX + '-preserving-kit-from-0.1.47.zip'), kit)
    archive(args.output / (PREFIX + '-evidence.zip'), evidence)
    files = {path.name: path.read_bytes() for path in args.output.iterdir() if path.is_file()}
    (args.output / 'SHA256SUMS.txt').write_bytes(checksums(files))
    print(json.dumps(dict(output=str(args.output), **metadata), indent=2))

if __name__ == '__main__':
    main()
