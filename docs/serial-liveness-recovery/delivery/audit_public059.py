#!/usr/bin/env python3
"""Offline .59 public-byte audit against independently obtained GitHub readbacks.

No fetching, publication, device access, source edits or historical cleanup.
All input paths are read-only. Only a new output receipt and disposable scratch
are written. Public assets must already include all 35 files. A fresh verifier
process is run; this is not a native rebuild or new hardware qualification.

Scratch: hard-link base/public files, reproduce one canonical ZIP at a time,
then run the published contract test using public-file hard links. No archive
is extracted to disk. Require 32 MiB free on the public-assets filesystem;
normal extra file payload is below 24 MiB. The preflight mode writes nothing.
"""
import argparse
import base64
import hashlib
import importlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
import zipfile

sys.dont_write_bytecode = True
MIB = 1024 * 1024
PRODUCT_REVISION = 'd0f95bfcfbef90df58f1bd6e8a3cfe5c495ab8eb'
RUNTIME_REVISION = '48229bd1593a2e24e95bf4537b495ee615990fd3'
HELPER_REVISION = '74f7491dc470b92dfa41fce41bf0c500f3714a94'
REPOSITORY = 'michaelrolphone-cmyk/RiscRTE-Wavshare-S3-Touch-AMOLED-2.06'
CI_RUN_ID = 39023362842
MODES = ('create', 'replace', 'known-lora')
LIMITS = dict(hash_chunk_bytes=MIB, json_bytes=8*MIB, public_assets=35,
              individual_asset_bytes=128*MIB, total_public_bytes=256*MIB,
              archive_members=20000, archive_member_bytes=64*MIB,
              archive_uncompressed_bytes=512*MIB, canonical_container_bytes=21*MIB,
              scratch_free_required_bytes=32*MIB, generated_file_bytes=24*MIB,
              subprocess_timeout_seconds=900, catalog_revision=1)


def require(value, message):
    if not value:
        raise ValueError(message)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def unique(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, 'Duplicate JSON key: ' + key)
        result[key] = value
    return result


def parse(data):
    require(len(data) <= LIMITS['json_bytes'], 'JSON exceeds 8 MiB')
    return json.loads(data, object_pairs_hook=unique,
                      parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))


def read_json(path):
    require(path.is_file() and not path.is_symlink(), 'Invalid JSON file: ' + str(path))
    require(path.stat().st_size <= LIMITS['json_bytes'], 'JSON exceeds 8 MiB: ' + str(path))
    return parse(path.read_bytes())


def file_record(path):
    require(path.is_file() and not path.is_symlink(), 'Invalid regular asset: ' + str(path))
    size = path.stat().st_size
    require(size <= LIMITS['individual_asset_bytes'], 'Asset exceeds 128 MiB: ' + path.name)
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(MIB), b''):
            h.update(chunk)
    return {'bytes': size, 'sha256': h.hexdigest()}


def same_files(left, right):
    if left.stat().st_size != right.stat().st_size:
        return False
    with left.open('rb') as a, right.open('rb') as b:
        while True:
            x, y = a.read(MIB), b.read(MIB)
            if x != y:
                return False
            if not x:
                return True


def git(root, *args):
    return subprocess.check_output(['git', '--no-optional-locks', '-C', str(root), *args], timeout=60)


def clean_source(root, revision):
    require(git(root, 'rev-parse', 'HEAD').decode().strip() == revision, 'Wrong source HEAD: ' + str(root))
    require(not git(root, 'status', '--porcelain'), 'Dirty source tree: ' + str(root))
    # This also resolves and verifies the immutable commit object before imports.
    require(git(root, 'rev-parse', revision + '^{commit}').decode().strip() == revision,
            'Source commit object missing: ' + str(root))


def checksum_rows(path):
    rows = {}
    for line in path.read_text(encoding='ascii').splitlines():
        require(re.fullmatch(r'[0-9a-f]{64}  [A-Za-z0-9._-]+', line) is not None,
                'Noncanonical checksum line: ' + path.name)
        hash_value, name = line.split('  ', 1)
        require(name not in rows, 'Duplicate checksum path: ' + name)
        rows[name] = hash_value
    require(rows, 'Empty checksum inventory: ' + path.name)
    return rows


def bounded_archive(path):
    with zipfile.ZipFile(path) as archive:
        rows = archive.infolist()
        require(len(rows) <= LIMITS['archive_members'], 'Too many archive members: ' + path.name)
        names = [row.filename for row in rows]
        require(len(names) == len(set(names)), 'Duplicate archive members: ' + path.name)
        require(sum(row.file_size for row in rows) <= LIMITS['archive_uncompressed_bytes'],
                'Archive expands beyond 512 MiB: ' + path.name)
        for row in rows:
            p = PurePosixPath(row.filename)
            require(not p.is_absolute() and '..' not in p.parts and '\\' not in row.filename,
                    'Unsafe archive name: ' + row.filename)
            require(row.file_size <= LIMITS['archive_member_bytes'], 'Archive member exceeds 64 MiB')
            require(not row.flag_bits & 1, 'Encrypted archive member')


def child_limits():
    import resource
    resource.setrlimit(resource.RLIMIT_FSIZE, (LIMITS['generated_file_bytes'], LIMITS['generated_file_bytes']))


def run_python(script, arguments, scratch, paths):
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', TMPDIR=str(scratch),
               PYTHONPATH=os.pathsep.join([*(str(p / 'scripts') for p in paths), os.environ.get('PYTHONPATH', '')]))
    result = subprocess.run([sys.executable, '-B', str(script), *map(str, arguments)],
                            capture_output=True, text=True, env=env,
                            timeout=LIMITS['subprocess_timeout_seconds'], preexec_fn=child_limits)
    require(result.returncode == 0,
            'Fresh process failed: ' + script.name + '\n' + result.stdout[-12000:] + result.stderr[-12000:])
    return result.stdout


def source_modules(a):
    for root, revision in ((a.product, a.revision), (a.runtime, RUNTIME_REVISION), (a.helper, HELPER_REVISION)):
        clean_source(root, revision)
    sys.path[:0] = [str(root / 'scripts') for root in (a.product, a.runtime, a.helper)]
    package = importlib.import_module('package_serial_liveness')
    pair_module = importlib.import_module('build_serial_liveness_pair')
    p = package.pins(final=True)
    require(p['runtime_revision'] == RUNTIME_REVISION and p['image_helper_revision'] == HELPER_REVISION,
            'Recovery source pins differ')
    require(p['version'] == '0.1.59' and p['publication_enabled'] is True, 'Wrong selected release')
    require(Path(package.ROOT).resolve() == a.product.resolve(), 'Imported package root differs')
    validator = pair_module.schema_module(a.runtime, a.schema, p)
    importlib.import_module('elftools.elf.elffile')
    return package, pair_module, validator, p


def check_baseline(a, package):
    from read_only_spiffs import read_image
    from prepare_preserving_update import layout, pair
    c = package.baseline_contract()
    for name, key in ((c['factory_asset'], 'factory'), ('store.bin', 'store'),
                      ('sd-apps.zip', 'external_archive'), ('SHA256SUMS', 'public_sha256sums')):
        require(file_record(a.baseline / name) == c[key], 'Public .58 baseline differs: ' + name)
    rows = checksum_rows(a.baseline / 'SHA256SUMS')
    for name in (c['factory_asset'], 'store.bin', 'sd-apps.zip'):
        require(rows[name] == file_record(a.baseline / name)['sha256'], 'Baseline checksum differs: ' + name)
    baseline = (a.baseline / c['factory_asset']).read_bytes()
    _, _, store = pair(baseline, 0, layout(baseline))
    require(store == (a.baseline / 'store.bin').read_bytes(), 'Baseline factory/store extraction differs')
    before = read_image(store, 0x550000)
    package.check_baseline(before, c)
    companion = package.companion_files(a.baseline / 'sd-apps.zip', c)
    return c, before, companion


def public_identity(a, p):
    metadata, tag, ci = map(read_json, (a.metadata, a.tag_metadata, a.ci_metadata))
    native_job = read_json(a.native_job_metadata)
    require(native_job['id'] == 117369424752 and native_job['run_id'] == a.ci_run_id and native_job['run_attempt'] == 1 and native_job['head_sha'] == a.revision and native_job['status'] == 'completed' and native_job['conclusion'] == 'success' and native_job['name'] == 'native', 'Exact successful native job missing')
    base = 'https://github.com/' + REPOSITORY
    api = 'https://api.github.com/repos/' + REPOSITORY
    require(type(metadata['id']) is int and metadata['id'] > 0, 'Missing actual GitHub release ID')
    require(metadata['draft'] is False and metadata['prerelease'] is True and
            metadata['target_commitish'] == a.revision and metadata['tag_name'] == p['release_tag'],
            'Release identity differs')
    require(metadata['html_url'] == base + '/releases/tag/' + p['release_tag'] and
            metadata['url'] == api + '/releases/' + str(metadata['id']), 'Release URL identity differs')
    require(tag['ref'] == 'refs/tags/' + p['release_tag'] and tag['object']['type'] == 'commit' and
            tag['object']['sha'] == a.revision, 'Actual release tag/source differs')
    require(ci['id'] == a.ci_run_id and ci['status'] == 'completed' and ci['conclusion'] == 'success' and
            ci['head_sha'] == a.revision and ci['repository']['full_name'] == REPOSITORY and
            ci['path'] == '.github/workflows/serial-liveness-native.yml', 'Successful exact-source native CI missing')
    rows = metadata['assets']
    require(len(rows) == LIMITS['public_assets'] and len({r['name'] for r in rows}) == len(rows),
            'Expected exactly 35 distinct public assets')
    require(a.public.is_dir() and not a.public.is_symlink(), 'Invalid public asset directory')
    require({f.name for f in a.public.iterdir()} == {r['name'] for r in rows}, 'Local/public inventories differ')
    require(sum(r['size'] for r in rows) <= LIMITS['total_public_bytes'], 'Public assets exceed 256 MiB')
    records = {}
    for row in rows:
        name = row['name']
        require(re.fullmatch(r'[A-Za-z0-9._-]+', name) is not None, 'Unsafe public asset name')
        record = file_record(a.public / name)
        require(row['state'] == 'uploaded' and type(row['id']) is int and row['id'] > 0 and
                row['size'] == record['bytes'] and row['digest'] == 'sha256:' + record['sha256'] and
                row['browser_download_url'] == base + '/releases/download/' + p['release_tag'] + '/' + name,
                'Public asset digest/identity differs: ' + name)
        records[name] = record
        if name.endswith('.zip'):
            bounded_archive(a.public / name)
    return metadata, tag, ci, native_job, records


def receipt_logs(archive, q, product, runtime, revision):
    """Check archived observations, not just detached qualification booleans."""
    from serial_liveness_release import check_serial_liveness
    from package_serial_liveness import pins
    check_serial_liveness(q, pins(final=True))
    from serial_wire_audit import verify_fixed_sources, validate_serial_wire_log
    wire_sources = verify_fixed_sources(product, runtime)
    result = {}
    for key, folder in (('serial_stat_boundaries', 'serial-stat-home'),
                        ('native_serial_scheduler', 'native-serial-liveness')):
        proof = q[key]
        prefix = 'build-evidence/' + folder + '/'
        require(parse(archive.read(prefix + 'qualification.json')) == proof, 'Embedded receipt differs: ' + key)
        checked = []
        for row in proof['cases']:
            parts = [row['build']]
            if 'group' in row:
                parts.append(row['group'])
            parts.append(row['case'])
            name = prefix + '-'.join(parts) + '.log'
            raw = archive.read(name)
            text = raw.decode('utf-8')
            require('runtime error:' not in text and 'ERROR: AddressSanitizer' not in text,
                    'Sanitizer error in actual log: ' + name)
            if key == 'serial_stat_boundaries':
                require(raw == (row['stdout'] + row['stderr']).encode(), 'Boundary log/receipt differs: ' + name)
            else:
                require(digest(raw) == row['log_sha256'], 'Scheduler log digest differs: ' + name)
                validate_serial_wire_log(raw, row['case'], row['build'])
                for marker in (
                    'CONFIRM_ACTIVE accepted=0 callback=1 strict=0 discovery_safe=1 continuing=1 session=1 pin=1 retained=0',
                    'CONFIRM_SETTLED accepted=1 strict=1 continuing=0 pin=0',
                    'FINAL ran=1 retained=0 error= lifecycle_retained=0 exit_safe=1 pinned=0 serial_retained=0'):
                    require(marker in text, 'Fixed scheduler observation missing: ' + marker)
                for operation in ('HELLO', 'NS 0', 'NS 1', 'PATH 0 2f6f6c642e747874'):
                    require('EXCHANGE op=' + operation + ' elapsed_ms=0 checkpoints=1 continuing=1 session=1 pin=1 pending=0 wire=RTEF1' in text,
                            'RAM-only command stalled under native custody: ' + operation)
                require(' -3 STAT' not in text and ' -6 STAT' not in text, 'Failed STAT observed in fixed scheduler')
                stat = re.search(r'EXCHANGE op=STAT 12 elapsed_ms=(\d+) checkpoints=(\d+) continuing=(\d+) session=(\d+) pin=(\d+) pending=(\d+) wire=RTEF1 12345678 5 ([^\n]+)', text)
                require(stat is not None, 'STAT observation missing')
                cadence = {'full-progress':1, 'full-pace8':8, 'full-pace16':16, 'full-pace32':32, 'full-slow':50, 'full-stall':1}[row['case']]
                require(int(stat[1]) == (int(stat[2]) - 1) * cadence, 'Measured scheduling cadence differs')
                if row['case'] in ('full-progress', 'full-pace8', 'full-pace16', 'full-pace32'):
                    require(int(stat[1]) < 4000 and stat[7] == '0 STAT 6 3' and stat.group(3,4,5,6) == ('0','0','0','0') and
                            'FULL_TRANSFER guarded-replace=1 create=1 readback=1 unrelated-preserved=1' in text,
                            'Complete guarded transfer/readback missing')
                else:
                    require(row['case'] in ('full-slow', 'full-stall') and int(stat[1]) == 4000 and stat[7] == '-4' and stat.group(3,4,5,6) == ('1','0','1','0') and
                            'FULL_TRANSFER' not in text, 'Deadline must fail safely with clean BUSY and no transfer')
            checked.append({'member': name, 'bytes': len(raw), 'sha256': digest(raw)})
        # Bind selected real source files to the exact local Git objects, despite
        # differing absolute CI workspace prefixes in the recorded input paths.
        source_rows = proof['inputs_sha256' if key == 'serial_stat_boundaries' else 'input_sha256']
        wanted = [(product, revision, 'scripts/test_serial_stat_home.py' if key == 'serial_stat_boundaries'
                   else 'scripts/test_native_serial_liveness.py'),
                  (product, revision, 'lib/storage_fatfs/fatfs/ff.c')]
        if key == 'native_serial_scheduler':
            wanted += [(runtime, RUNTIME_REVISION, name) for name in (
                'src/bootstrap/Runtime.cpp', 'src/runtime/serial/Files.cpp', 'src/ports/esp32s3/CpuPort.cpp',
                'src/ports/esp32s3/NativeSettingsLifecycle.cpp', 'src/ports/esp32s3/NativeSettingsMaintenance.cpp',
                'src/ports/esp32s3/NativeSettingsBootstrap.cpp')]
            wanted += [(product, revision, name) for name in ('tests/native_serial_liveness/sd_fixture.c',
                'tests/native_serial_liveness/prepare.py', 'tests/native_serial_liveness/full_transfer_fixture.inc')]
            for build in ('normal', 'sanitized'):
                log = archive.read(prefix + build + '-compile.log').decode()
                compilation = next(row for row in proof['compilations'] if row['build'] == build)
                for command in compilation['commands']:
                    require(json.dumps(command) + '\n' in log, 'Scheduler compile-log/receipt differs')
        for root, rev, name in wanted:
            matches = [value for path, value in source_rows.items() if path.endswith('/' + name)]
            require(matches == [digest(git(root, 'show', rev + ':' + name))], 'Actual source receipt differs: ' + name)
        result[key] = {'cases': len(checked), 'archived_logs_verified': checked,
                       'selected_source_custody_verified': len(wanted), 'wire_source_custody': wire_sources if key == 'native_serial_scheduler' else None, 'complete_wire_trace_verified': key == 'native_serial_scheduler', 'hardware_tested': False,
                       'target_instructions_executed': False}
    return result


def feed_readback(a, p, base):
    require(a.feed.is_file() and not a.feed.is_symlink() and a.feed.stat().st_size <= MIB, 'Raw feed exceeds 1 MiB or is not a regular file')
    raw = a.feed.read_bytes()
    require(len(raw) <= MIB and raw == (base / 'native-packages-v1.json').read_bytes(),
            'Raw versioned feed differs from release bytes')
    metadata = read_json(a.feed_metadata)
    name = p['version'] + '/native-packages-v1.json'
    require(metadata['type'] == 'file' and metadata['path'] == name and metadata['encoding'] == 'base64' and
            metadata['size'] == len(raw) and metadata['download_url'] == p['feed_url'], 'Feed API identity differs')
    require(base64.b64decode(metadata['content']) == raw, 'Feed API/raw response differs')
    blob = hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()
    require(metadata['sha'] == blob, 'Feed Git blob custody differs')
    value = parse(raw)
    require(len(value['boot_profiles']['core']['profile']['files']) == 111 and
            value['boot_profiles']['core']['mirrors'] == [] and value['apps'] == [] and
            value['profiles'] == {'core': []}, 'Feed is not exact internal-only core')
    return {'url': p['feed_url'], 'bytes': len(raw), 'sha256': digest(raw), 'git_blob_sha': blob,
            'public_bytes_match': True, 'core_files': 111, 'internal_only': True,
            'version_specific_path': True, 'future_remote_immutability_not_proven': True}


def canonical_pairs(a, p, pair_module, base, scratch):
    merged = None
    for mode in MODES:
        with tempfile.TemporaryDirectory(prefix='canonical-' + mode + '-', dir=scratch) as temp:
            output = Path(temp) / 'candidate'
            previous_modes = pair_module.PAIR_MODES
            try:
                # The pinned producer still constructs all metadata and bytes;
                # only its outer emission loop is narrowed to one variant.
                pair_module.PAIR_MODES = (mode,)
                report = pair_module.build(base, a.metadata, a.runtime, a.schema, output, catalog_revision=1)
            finally:
                pair_module.PAIR_MODES = previous_modes
            stem = 'Waveshare-' + p['version'] + '-SD-Apps-' + mode
            for local, public in ((stem+'.zip', stem+'.zip'), (stem+'.json', stem+'.json'),
                                  ('context.json', stem+'-context.json'), ('descriptor.json', stem+'-descriptor.json')):
                produced = output / mode / local
                if local.endswith('.zip'):
                    require(produced.stat().st_size <= LIMITS['canonical_container_bytes'], 'Canonical container exceeds 21 MiB')
                require(same_files(produced, a.public / public), 'Canonical bytes differ: ' + public)
            if merged is None:
                merged = report
            else:
                require({k:v for k,v in report.items() if k != 'results'} ==
                        {k:v for k,v in merged.items() if k != 'results'}, 'Variant report identities differ')
                merged['results'].update(report['results'])
        print('Canonical ' + mode + ' bytes PASS', flush=True)
    # Test all three actual public containers without copying them. The pinned
    # contract test creates at most one disposable modified-container fixture.
    with tempfile.TemporaryDirectory(prefix='contract-', dir=scratch) as temp:
        candidate = Path(temp) / 'candidate'
        candidate.mkdir()
        for mode in MODES:
            folder = candidate / mode
            folder.mkdir()
            stem = 'Waveshare-' + p['version'] + '-SD-Apps-' + mode
            for local, public in ((stem+'.zip', stem+'.zip'), (stem+'.json', stem+'.json'),
                                  ('context.json', stem+'-context.json'), ('descriptor.json', stem+'-descriptor.json')):
                os.link(a.public / public, folder / local)
        tests = parse(run_python(a.product / 'scripts/test_serial_liveness_pair.py',
                                 ['--candidate', candidate, '--schema', a.schema],
                                 Path(temp), (a.product, a.runtime, a.helper)))
    require(tests['status'] == 'passed' and tests['positive_candidates'] == 3 and tests['rejection_count'] == 45,
            'Fresh canonical contract matrix differs')
    merged['contract_tests'] = tests
    require(read_json(a.public / 'PAIR-QUALIFICATION.json') == merged, 'Public pair qualification differs from reconstruction')
    return merged


def audit(a):
    require(__debug__, 'Do not run Python with -O')
    require(a.revision == PRODUCT_REVISION and a.ci_run_id == CI_RUN_ID, 'This helper is scoped to the selected .59 producer/CI run')
    package, pair_module, validator, p = source_modules(a)
    contract, before, companion = check_baseline(a, package)
    if a.preflight:
        print(json.dumps({'status': 'preflight-passed', 'public_release_audited': False,
                          'source_revision': a.revision, 'runtime_revision': RUNTIME_REVISION,
                          'baseline_internal_files': len(before), 'baseline_external_files': len(companion),
                          'limits': LIMITS}, indent=2))
        return
    protected = [path.resolve() for path in (a.product, a.runtime, a.helper, a.baseline, a.public)]
    require(not any(a.output.resolve().is_relative_to(path) for path in protected), 'Audit output must be outside source and input trees')
    require(not a.output.exists(), 'Output must be new; historical receipts are never replaced')
    require(a.output.parent.is_dir(), 'Output parent must exist')
    require(re.fullmatch('[0-9a-f]{64}', a.expected_sha) is not None, 'Exact expected SHA256SUMS digest required')
    readback_names = ('metadata', 'tag_metadata', 'ci_metadata', 'native_job_metadata', 'feed', 'feed_metadata')
    input_records = {name: file_record(getattr(a, name)) for name in readback_names}
    metadata, tag, ci_run, native_job, assets = public_identity(a, p)
    from publish_serial_liveness_release import pair_asset_names
    from serial_liveness_release import release_names
    q = read_json(a.public / 'qualification.json')
    expected_base, _ = release_names(p, q)
    sidecars = pair_asset_names(p['version'])
    require(set(assets) == expected_base | sidecars and len(expected_base) == 21 and len(sidecars) == 14,
            'Public base/canonical inventory differs')
    require(assets['SHA256SUMS']['sha256'] == a.expected_sha, 'Expected SHA256SUMS custody differs')
    for sums, expected in (('SHA256SUMS', expected_base - {'SHA256SUMS'}),
                           ('PAIR-SHA256SUMS', sidecars - {'PAIR-SHA256SUMS'})):
        rows = checksum_rows(a.public / sums)
        require(set(rows) == expected and all(assets[name]['sha256'] == value for name, value in rows.items()),
                'Checksum file coverage/digests differ: ' + sums)
    scratch_parent = a.scratch_parent or a.public.parent
    require(not any(scratch_parent.resolve().is_relative_to(path) for path in protected), 'Scratch must be outside source and input trees')
    require(scratch_parent.stat().st_dev == a.public.stat().st_dev,
            'Scratch must share the public-assets filesystem for hard links; no copying fallback')
    require(shutil.disk_usage(scratch_parent).free >= LIMITS['scratch_free_required_bytes'],
            'At least 32 MiB additional scratch free space required; no historical cleanup is attempted')
    with tempfile.TemporaryDirectory(prefix='wave59-audit-', dir=scratch_parent) as temp:
        scratch = Path(temp)
        base = scratch / 'base'
        base.mkdir()
        for name in sorted(expected_base):
            os.link(a.public / name, base / name)
        run_python(a.product / 'scripts/serial_liveness_release.py',
                   ['--verify', base, '--expected-sha', a.expected_sha, '--source-revision', a.revision],
                   scratch, (a.product, a.runtime, a.helper))
        print('All 35 public hashes, exact source and fresh release verifier PASS', flush=True)
        from prepare_preserving_update import pair, layout
        from read_only_spiffs import read_image
        from store_image_capacity import inspect
        factory_name = 'Waveshare-' + p['version'] + '-SD-Apps-factory-erases-data-0x0.bin'
        factory = (base / factory_name).read_bytes()
        require(len(factory) == 16777216, 'Factory must be exactly 16 MiB')
        _, firmware, store = pair(factory, 0, layout(factory))
        require(firmware == (base / 'firmware.bin').read_bytes() and store == (base / 'store.bin').read_bytes(),
                'Independent factory extraction differs')
        after = read_image(store, 0x550000)
        reconstructed, payload, preservation = package.compose(before, companion,
            {name: after[name] for name in p['store_replacements']}, p, a.revision, firmware)
        require(after == reconstructed and preservation == q['preservation'], 'Exact .58 store reconstruction differs')
        with zipfile.ZipFile(base / 'sd-apps.zip') as z:
            require({name:z.read(name) for name in z.namelist()} == payload == companion,
                    'The 45 SD files changed from public .58')
        require(same_files(base / 'sd-apps.zip', a.baseline / 'sd-apps.zip'), 'SD archive bytes changed from public .58')
        from build_serial_liveness_native import linked_provisioning_layout
        from radio_iq_proof import prove
        with zipfile.ZipFile(base / ('Waveshare-' + p['version'] + '-SD-Apps-Evidence.zip')) as z:
            elf_row = q['input_lock']['native_files']['firmware_elf']
            native = z.read('build/' + elf_row['path'])
            require(package.record(native) == {k:elf_row[k] for k in ('bytes', 'sha256')}, 'Actual linked ELF custody differs')
            linked = linked_provisioning_layout(native)
            require(linked == q['provisioning']['linked_layout'], 'Actual linked DWARF/layout differs')
            iq = json.loads(json.dumps(prove(native, q['native']['radio_iq']['target_identity'])))
            require(iq == q['native']['radio_iq'] and iq['bank_bytes'] == 65536, 'Recomputed final-link IQ proof differs')
            serial = receipt_logs(z, q, a.product, a.runtime, a.revision)
        with zipfile.ZipFile(base / 'ci-provenance.zip') as z:
            ci = parse(z.read('ci-run.json'))
            require(parse(z.read('iq-linked.json')) == iq, 'CI/actual linked IQ custody differs')
        require(ci['GITHUB_SHA'] == ci['GITHUB_WORKFLOW_SHA'] == a.revision and
                int(ci['GITHUB_RUN_ID']) == a.ci_run_id and int(ci['GITHUB_RUN_ATTEMPT']) == native_job['run_attempt'] <= ci_run['run_attempt'],
                'Actual native CI provenance differs')
        require(ci['GITHUB_REF'] == 'refs/heads/' + ci_run['head_branch'], 'CI run/ref custody differs')
        feed = feed_readback(a, p, base)
        report = canonical_pairs(a, p, pair_module, base, scratch)
        receipt = {'schema': 1, 'checked_at': datetime.now(timezone.utc).isoformat(),
            'source_revision': a.revision, 'runtime_revision': RUNTIME_REVISION,
            'release_id': metadata['id'], 'release_url': metadata['html_url'],
            'public_asset_count': len(assets), 'public_assets': assets,
            'all_public_asset_digests_verified': True, 'full_release_verifier_passed': True,
            'checksums_sha256': a.expected_sha, 'pair_checksums_sha256': assets['PAIR-SHA256SUMS']['sha256'],
            'independent_factory_extraction': True, 'factory': package.record(factory),
            'firmware': package.record(firmware), 'store': package.record(store),
            'baseline': {'source_revision': contract['source_revision'], 'factory': contract['factory'],
                         'store': contract['store'], 'sd_archive': contract['external_archive']},
            'preservation': preservation, 'sd_archive_byte_identical': True, 'capacity': inspect(store),
            'packing': q['packing'], 'linked_layout': linked, 'iq': iq, 'native_ci': ci,
            'native_ci_readback': {'id':ci_run['id'], 'attempt':native_job['run_attempt'], 'job_id':native_job['id'],
                                   'conclusion':native_job['conclusion'], 'html_url':native_job['html_url']},
            'publication_ci_readback': {'id':ci_run['id'], 'attempt':ci_run['run_attempt'], 'conclusion':ci_run['conclusion'], 'html_url':ci_run['html_url']},
            'publisher_retry': 'Attempt1 final public download connection reset; only failed publisher job retried with the same native artifact.',
            'actual_serial_receipts': serial,
            'navigation': {'passed':q['navigation']['passed'], 'cases':len(q['navigation']['tests']), 'hardware_tested':False},
            'canonical_pair': {'variants':list(MODES), 'reproduced_byte_identical':True,
                'release_id':report['github_release_id'], 'expected_catalog_revision':1,
                'catalog_identity_requires_readback':True, 'contract_tests':report['contract_tests']},
            'feed': feed, 'limits': LIMITS, 'hardware_tested': False, 'target_instructions_executed':False,
            'device_accessed':False, 'factory_erases_internal_data':True,
            'native_build_reexecuted':False, 'network_requests_performed':False,
            'readback_freshness_is_callers_responsibility':True,
            'catalog_association_or_live_readback_performed':False,
            'input_readbacks': input_records}
        # Recheck every public hash after validation to catch concurrent changes.
        require({name:file_record(a.public/name) for name in assets} == assets, 'Public inputs changed during audit')
        require({name:file_record(getattr(a,name)) for name in readback_names} == input_records, 'Metadata/feed readbacks changed during audit')
        for root, revision in ((a.product,a.revision),(a.runtime,RUNTIME_REVISION),(a.helper,HELPER_REVISION)):
            clean_source(root, revision)
        with a.output.open('x', encoding='utf-8') as target:
            target.write(json.dumps(receipt, sort_keys=True, indent=2) + '\n')
    print(json.dumps({k:receipt[k] for k in ('source_revision','release_id','public_asset_count','factory',
                                          'store','canonical_pair','hardware_tested')}, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    defaults = {'product':'/tmp/wave-sd-successor/product', 'runtime':'/tmp/runtime-stat-fix-20261017',
                'schema':'/tmp/wave-paired-20261017/replay-ci/schema', 'helper':'/tmp/twatch-provision-20261016/helper',
                'baseline':'/tmp/wave-stat-retention-20261017/public058'}
    for name, value in defaults.items():
        parser.add_argument('--' + name, type=Path, default=Path(value))
    for name in ('public','metadata','tag-metadata','ci-metadata','native-job-metadata','feed','feed-metadata','output','scratch-parent'):
        parser.add_argument('--' + name, type=Path)
    parser.add_argument('--expected-sha', help='Independently retained SHA256SUMS SHA-256')
    parser.add_argument('--revision', default=PRODUCT_REVISION)
    parser.add_argument('--ci-run-id', type=int, default=CI_RUN_ID)
    parser.add_argument('--preflight', action='store_true', help='Read-only source/schema/baseline readiness; no public .59 claim')
    a = parser.parse_args()
    if not a.preflight:
        missing = [name for name in ('public','metadata','tag_metadata','ci_metadata','native_job_metadata','feed','feed_metadata','output','expected_sha')
                   if getattr(a,name) is None]
        if missing:
            parser.error('Audit requires ' + ', '.join('--' + name.replace('_','-') for name in missing))
    for name, value in vars(a).items():
        if isinstance(value,Path):
            # Do not resolve away a final symlink before the regular-file check.
            setattr(a,name,value.absolute())
    try:
        audit(a)
    except (ValueError, KeyError, OSError, ImportError, AssertionError, subprocess.SubprocessError, zipfile.BadZipFile) as exc:
        print('AUDIT FAILED: ' + str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
