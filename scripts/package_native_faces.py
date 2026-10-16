#!/usr/bin/env python3
"""Build and qualify native-resolution Home over the exact official 0.1.46 store."""
import argparse, hashlib, io, json, os, re, subprocess, sys, tempfile, zipfile
from pathlib import Path
import package_crash_sdr as baseline_tools
from package_crash_sdr import require, sha, encoded, git_bytes, checksums, archive, verify_trace_storage
ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / 'docs/native-faces'
PINS = json.loads((DOCS / 'source-pins.json').read_text())
PREFIX = 'Waveshare-0.1.47-Native-Faces'
FACTORY = PREFIX + '-factory-erases-data-0x0.bin'
RUNTIME_HELPERS = baseline_tools.RUNTIME_HELPERS
PRODUCT_INPUTS = baseline_tools.PRODUCT_INPUTS + (
    'scripts/package_native_faces.py', 'scripts/test_native_faces_release.py',
    'scripts/qualify_native_faces.py', 'scripts/stage_faces_baseline_native.py',
    'scripts/verify_native_faces_admission.py',
    'docs/native-faces/source-pins.json', 'docs/native-faces/RELEASE-NOTES.txt',
    'docs/native-faces/PRESERVING-UPDATE.txt', 'docs/native-faces/RELEASE-ROUTE.txt', 'docs/native-faces/prepare.py',
    'docs/native-faces/verify_readbacks.py', '.github/workflows/native-faces-release.yml',
)

def run(*args, **kwargs):
    kwargs['env'] = {**os.environ, **kwargs.get('env', {}), 'PYTHONDONTWRITEBYTECODE': '1'}
    return baseline_tools.run(*args, **kwargs)

def verify_final_pins():
    require(PINS['finalized'] is True and type(PINS['publication_enabled']) is bool, 'Final pins and explicit publication gate required')
    require((PINS['version'], PINS['baseline_version'], PINS['release_tag']) == ('0.1.47', '0.1.46', 'test-native-faces-0.1.47'), 'Release identity mismatch')
    require(PINS['baseline_product'] == '38b84ae7965512b79a2211c72c8de1f9488790c8', 'Exact official .46 source required')
    require(PINS['runtime_revision'] == baseline_tools.PINS['runtime_revision'], 'Native Runtime must remain unchanged')
    require(PINS['native_changed'] is False and PINS['changed_store_files'] == ['cohort.json','default.elf','default.json'], 'Home-only change allowlist required')
    require(PINS['home_version'] == '0.16.0' and PINS['preferences'] == 'atomic' and PINS['crash_volume'] == 12, 'Exact Home composition required')
    for key in ('watch_revision','system_revision','utilities_revision','image_helper_revision','vendor_revision'):
        require(re.fullmatch('[0-9a-f]{40}', PINS[key]), 'Immutable revision missing: ' + key)
    for key in ('baseline_sha256','baseline_evidence_sha256','home_sha256','baseline_home_sha256','baseline_native_sha256','baseline_native_elf_sha256'):
        require(re.fullmatch('[0-9a-f]{64}', PINS[key]), 'Digest missing: ' + key)
    require(PINS['baseline_sha256'] == 'ae9cfc06ba62cb6bd0ccd91a93166c9319f92991189e40724b833b7363f67583', 'Exact baseline digest required')
    require(PINS['baseline_evidence_sha256'] == '2863260b75f2ac22083c934a04ca3c644de4c341cb75d98a1ae919ff0d20d7ee', 'Exact native evidence required')

def verify_baseline_bytes(data):
    require(len(data) == 0x1000000 and sha(data) == PINS['baseline_sha256'], 'Exact released .46 factory required')

def replace_home(before, home):
    require(sha(before['default.elf']) == PINS['baseline_home_sha256'], 'Baseline Home mismatch')
    require(sha(home) == PINS['home_sha256'] and len(home) == PINS['home_bytes'] and home != before['default.elf'], 'Rebuilt Home mismatch')
    require(home[:7] == b'\x7fELF\x01\x01\x01' and home[16:20] == b'\x03\x00\x5e\x00', 'Expected ELF32 Xtensa ET_DYN Home')
    manifest = json.loads(before['default.json'])
    require(manifest['version'] == PINS['baseline_home_version'], 'Baseline Home version mismatch')
    result = dict(before)
    result['default.elf'] = home
    result['default.json'] = (json.dumps(dict(manifest, version=PINS['home_version']), separators=(',', ':')) + '\n').encode()
    return result

def verify_changed_store(before, store):
    require(set(before) == set(store), 'Store member set changed')
    changed = sorted(name for name in before if before[name] != store[name])
    require(changed == PINS['changed_store_files'], 'Unapproved store changes: ' + str(changed))
    require(sum(name.endswith('.elf') for name in store) == 62, 'Complete 62-ELF baseline required')
    require(sha(store['default.elf']) == PINS['home_sha256'], 'Home ELF mismatch')
    require(json.loads(store['default.json']) == dict(json.loads(before['default.json']), version=PINS['home_version']), 'Home manifest changed beyond version')
    require(sha(store['springboard.elf']) == PINS['baseline_springboard_sha256'], 'Springboard changed')
    return changed

def verify_watch_source(watch):
    require(run('git','-C',watch,'rev-parse','HEAD').strip() == PINS['watch_revision'], 'Watch source revision mismatch')
    require(not run('git','-C',watch,'status','--porcelain','--untracked-files=all','--','apps','include','sdk','scripts','tests','dependencies.lock.json').strip(), 'Watch input tree is dirty')
    lock=json.loads((watch/'dependencies.lock.json').read_text())
    require(lock['system']['commit'] == PINS['system_revision'] and lock['utilities']['commit'] == PINS['utilities_revision'], 'Watch dependency lock differs')
    return {name: sha(git_bytes(watch,PINS['watch_revision'],name)) for name in run('git','-C',watch,'ls-files','-z','apps','include','sdk','scripts','tests','dependencies.lock.json').rstrip('\0').split('\0')}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('baseline', 'evidence', 'runtime', 'watch', 'system', 'compiler', 'image-helper', 'vendor', 'utilities', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--source-revision', required=True)
    args = parser.parse_args()
    require(__debug__, 'Do not run with Python -O')
    verify_final_pins()
    product_source_hashes = baseline_tools.verify_product_source(ROOT, args.source_revision, PRODUCT_INPUTS)
    require(not args.output.exists() or not any(args.output.iterdir()), 'Output must be empty')
    runtime, image_helper = args.runtime.resolve(), args.image_helper.resolve()
    native_dir = runtime / '.pio/build/waveshare-t051'
    require(native_dir == runtime / '.pio/build/waveshare-t051', 'Native output must be selected waveshare-t051 build')
    source_hashes = baseline_tools.verify_sources(runtime, image_helper, args.vendor.resolve())
    watch_source_hashes = verify_watch_source(args.watch.resolve())
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
    require(original['version'] == '0.1.46' and original['source_revision'] == PINS['baseline_product'], 'Baseline cohort identity mismatch')
    require(sha(before['springboard.elf']) == PINS['baseline_springboard_sha256'], 'Baseline native-vector Springboard mismatch')
    from stage_faces_baseline_native import verified_native
    native, native_custody = verified_native(baseline, args.evidence)
    require(all((native_dir / name).read_bytes() == native[name] for name in ('firmware.bin','firmware.elf','partitions.bin')), 'Admission native files differ from official baseline')
    firmware = native['firmware.bin']
    require(0 < len(firmware) <= 0x260000, 'Bounded native firmware required')
    require((firmware != old_native) == PINS['native_changed'], 'Native changed status differs from finalized pins')
    require(sha(old_native) == PINS['baseline_native_sha256'], 'Baseline native hash mismatch')
    esp_image(firmware)
    elf(native['firmware.elf'])
    baseline_tools.verify_native_identity(native)
    require(sha(native['firmware.elf']) == PINS['baseline_native_elf_sha256'], 'Official .46 native ELF changed')
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
    require(native['partitions.bin'] == baseline[0x8000:0x8000 + len(native['partitions.bin'])], 'Native partition layout differs from installed .46')
    require(native_custody == dict(baseline_product=PINS['baseline_product'], runtime_revision=PINS['runtime_revision'], baseline_factory_sha256=PINS['baseline_sha256'], baseline_evidence_sha256=PINS['baseline_evidence_sha256'], native_sha256=sha(firmware), native_elf_sha256=sha(native['firmware.elf']), native_reused_unchanged=True), 'Native custody receipt differs')
    proof['official_baseline_custody'] = native_custody
    proof.update(native_source_product_revision=baseline_tools.PINS['baseline_product'], native_reused_unchanged=True, baseline_evidence_sha256=PINS['baseline_evidence_sha256'], runtime_revision=PINS['runtime_revision'], bin_sha256=sha(firmware), elf_sha256=sha(native['firmware.elf']), elf_bin_identical=True, source_hashes=source_hashes)
    with tempfile.TemporaryDirectory(prefix='native-home-build-') as td:
        target = Path(td) / 'target'
        run(sys.executable, args.watch.resolve() / 'scripts/build.py', '--system', args.system.resolve(), '--utilities', args.utilities.resolve(), '--cc', args.compiler.resolve(), '--role', 'default', '--preferences', 'atomic', '--crash-volume', '12', '--output', target)
        target_proof = json.loads((target/'build.json').read_text())
        home = (target/'default.elf').read_bytes()
        require(target_proof['artifacts']['default']['sha256'] == PINS['home_sha256'] and target_proof['preferences'] == 'atomic', 'Source replay receipt differs')
        require('-DWATCH_CRASH_REPORT_VOLUME=12' in target_proof['artifacts']['default']['defines'], 'Crash volume differs')
        require(target_proof['compiler'] == PINS['compiler_version'], 'Compiler identity differs')
        require(all(watch_source_hashes.get(name) == digest for name,digest in target_proof['home_files_sha256'].items()), 'Watch build inputs differ from Git source')
        replay_files = {'build.json': encoded(target_proof)}
    require(watch_source_hashes == verify_watch_source(args.watch.resolve()), 'Watch source changed during rebuild')
    springboard = before['springboard.elf']
    store = replace_home(before, home)
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
    with tempfile.TemporaryDirectory(prefix='native-home-qualification-') as td:
        qualified = Path(td) / 'results'
        run(sys.executable, ROOT/'scripts/qualify_native_faces.py', '--watch', args.watch.resolve(), '--system', args.system.resolve(), '--utilities', args.utilities.resolve(), '--output', qualified)
        source_qualification = json.loads((qualified/'qualification.json').read_text())
        qualification_files = {p.relative_to(qualified).as_posix(): p.read_bytes() for p in qualified.rglob('*') if p.is_file() and p.suffix in ('.json','.log')}
    helpers = {name: (runtime / 'scripts' / name).read_bytes() for name in RUNTIME_HELPERS}
    require(all(data == git_bytes(runtime, PINS['runtime_revision'], 'scripts/' + name) for name, data in helpers.items()), 'Preserving helper source mismatch')
    metadata = dict(PINS, source_revision=args.source_revision, candidate_sha256=sha(candidate), native_sha256=sha(firmware), native_elf_sha256=sha(native['firmware.elf']), hardware_tested=False, device_accessed=False, verified_hardware_fix=False, system_unchanged=False, native_changed=PINS['native_changed'], all_other_store_payloads_unchanged=True, springboard_sha256=sha(springboard), springboard_manifest_sha256=sha(store['springboard.json']), home_elf_sha256=sha(store['default.elf']), retained_wake_policy_added=False, springboard_unchanged=True, replayed_app_count=1, changed_app_count=1, unchanged_elf_count=61, includes_t023_provisioning=False, factory_erases_saved_data=True, sd_unchanged=True)
    metadata['artifact_sources'] = {'native': {'runtime_revision': PINS['runtime_revision'], 'product_revision': baseline_tools.PINS['baseline_product'], 'official_evidence_sha256': PINS['baseline_evidence_sha256'], 'reused_byte_identically': True}, 'home': {'watch_revision': PINS['watch_revision'], 'system_revision': PINS['system_revision'], 'utilities_revision': PINS['utilities_revision'], 'sha256': sha(home), 'preferences': 'atomic', 'crash_volume': 12}}
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
    require(watch_source_hashes == verify_watch_source(args.watch.resolve()), 'Watch sources changed during packaging')
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / FACTORY).write_bytes(candidate)
    (args.output / 'release.json').write_bytes(encoded(metadata))
    (args.output / 'RELEASE-NOTES.txt').write_text(notes)
    (args.output / 'decode_display_perf.py').write_bytes((ROOT / 'scripts/decode_display_perf.py').read_bytes())
    (args.output / 'DISPLAY-TIMING.md').write_bytes((ROOT / 'docs/NATIVE_DISPLAY_TIMING.md').read_bytes())
    archive(args.output / (PREFIX + '-preserving-kit-from-0.1.46.zip'), kit)
    archive(args.output / (PREFIX + '-evidence.zip'), evidence)
    files = {path.name: path.read_bytes() for path in args.output.iterdir() if path.is_file()}
    (args.output / 'SHA256SUMS.txt').write_bytes(checksums(files))
    print(json.dumps(dict(output=str(args.output), **metadata), indent=2))

if __name__ == '__main__':
    main()
