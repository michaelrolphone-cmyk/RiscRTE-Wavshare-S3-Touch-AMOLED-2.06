#!/usr/bin/env python3
"""Verify and transport same-run native candidates; never attest detached builds."""
import argparse
import io
import json
from pathlib import Path
import re
import sys
import zipfile

import package_minimal_sd as package
import native_idf61_candidate as native
from package_minimal_sd import require, record, sha, encoded
from transport_native_idf61_release import archive_members, checksums, decode
from package_alarm_sleep import make_archive

NATIVE = {'factory-candidate-erases-data-0x0.bin', 'firmware.bin', 'bootloader.bin', 'partitions.bin', 'store.bin'}
PAYLOAD = {'sd-apps.zip','sd-inventory.json'}
CANDIDATE = NATIVE | PAYLOAD | {'qualification.json', 'source-lock.json', 'source-pins.json', 'default.elf', 'default.json', 'candidate-evidence.zip', 'SHA256SUMS', 'native-packages-v1.json', 'feed-qualification.json'}
ROLES = {'product', 'runtime', 'system', 'utilities', 'drivers', 'sdk', 'watch', 'image_helper'}
PRODUCTS = {'twatch': ('RiscRTE-T-Watch-S3', 'TWatch'), 'waveshare': ('RiscRTE-Wavshare-S3-Touch-AMOLED-2.06', 'Waveshare')}


def feed_names(q):
    require('store.bin' in q['artifacts'], 'Store artifact missing')
    rows = q['feed']['receipt']['assets']
    require(len(rows) == 1 and set(rows) == {'bootfs-' + q['artifacts']['store.bin']['sha256'] + '.bin'}, 'Exact internal bootfs asset required')
    return set(rows) | {'native-packages-v1.json', 'feed-qualification.json'}


def check_feed_qualification(feed):
    receipt, controller = feed['receipt'], feed['controller']
    require(receipt['credential_free'] is True and receipt['file_count'] == 111 and receipt['product'] == 'waveshare-s3-touch-amoled-206' and receipt['profile'] == 'core' and receipt['wifi_headroom'] >= 512, 'Complete bounded credential-free core required')
    require(feed['core_inventory_files'] == 111 and feed['core_inventory_elfs'] == 43 and feed['dynamic_app_descriptors'] == 0 and feed['hardware_tested'] is False, 'Feed scope differs')
    require(controller['files_selected'] == 111 and controller['queue_calls'] == 1 and controller['exact_image_url_size_digest_selected'] is True and controller['native_firmware_identity_matched'] is True and controller['hardware_tested'] is False and controller['target_instructions_executed'] is False, 'Production controller proof missing')
    require(controller['production_feed_sha256'] == receipt['feed_sha256'], 'Controller/feed digest mismatch')


def verify_feed_assets(root, q, names=None):
    names = names or {}; path = lambda n: root / names.get(n, n)
    feed = decode(path('native-packages-v1.json').read_bytes())
    proof = decode(path('feed-qualification.json').read_bytes())
    require(proof == q['feed'], 'Feed qualification differs')
    require(sha(path('native-packages-v1.json').read_bytes()) == proof['receipt']['feed_sha256'], 'Feed digest differs')
    core = feed['boot_profiles']['core']; profile = core['profile']
    require(len(profile['files']) == 111 and not core['mirrors'] and feed['apps'] == [] and feed['profiles'] == {'core': []}, 'Feed scope differs')
    store = q['artifacts']['store.bin']; firmware = q['artifacts']['firmware.bin']
    name = 'bootfs-' + store['sha256'] + '.bin'
    require(path(name).read_bytes() == path('store.bin').read_bytes(), 'Feed bootfs differs')
    require(profile['image']['sha256'] == store['sha256'] and profile['image']['bytes'] == store['bytes'], 'Feed image differs')
    require(core['native']['firmware_sha256'] == firmware['sha256'] and core['native']['firmware_size'] == firmware['bytes'], 'Feed native identity differs')
    expected = 'https://github.com/michaelrolphone-cmyk/RiscRTE-Wavshare-S3-Touch-AMOLED-2.06/releases/download/' + package.pins()['release_tag'] + '/' + name
    require(profile['image']['url'] == expected, 'Immutable feed source differs')


def check_directory(root, expected_sha=None, expected_names=None):
    require(root.is_dir() and not root.is_symlink(), 'Invalid output directory')
    sums_file = root / 'SHA256SUMS'
    require(sums_file.is_file() and not sums_file.is_symlink(), 'Missing checksum custody')
    data = sums_file.read_bytes()
    if expected_sha is not None: require(sha(data) == expected_sha, 'Checksum custody differs')
    rows = checksums(data)
    names = {p.name for p in root.iterdir()}
    require(names == set(rows) | {'SHA256SUMS'}, 'Output inventory differs')
    if expected_names is not None: require(names == expected_names, 'Unexpected candidate inventory')
    for name, digest in rows.items():
        path = root / name
        require(path.is_file() and not path.is_symlink() and sha(path.read_bytes()) == digest, 'Asset changed: ' + name)
    return rows


def check_qualification(q, p, revision):
    require(re.fullmatch('[0-9a-f]{40}', revision), 'Immutable product revision required')
    require(q['schema'] == 1 and q['status'] == 'software-qualified-candidate-hardware-pending', 'Native qualification required')
    require(q['product'] == p['product'] and q['version'] == p['version'] and q['source_revision'] == revision, 'Candidate identity differs')
    for key, value in {'hardware_tested': False, 'device_accessed': False,
                       'factory_erases_data': True, 'preserving_update_kit_emitted': False, 'native_rebuilt': True}.items():
        require(q.get(key) is value, 'Qualification limits differ: ' + key)
    lock = q['input_lock']
    require(lock['schema'] == 1 and lock['publication_enabled'] is False and lock['candidate_version'] == p['version'], 'Source lock identity differs')
    require(set(lock['sources']) == ROLES, 'Incomplete source closure')
    for role, row in lock['sources'].items():
        require(row['revision'] == (revision if role == 'product' else p[role + '_revision']), 'Source revision differs: ' + role)
        require(re.fullmatch('[0-9a-f]{40}', row['tree']) and isinstance(row['submodules'], list), 'Malformed source closure')
        require(all(re.fullmatch('[0-9a-f]{40} [^\n\r]+', s) for s in row['submodules']), 'Malformed submodule closure')
    proof = q['controlled_build']
    require(proof['fresh_build'] is True and proof['same_process_qualification'] is True
            and proof['detached_receipt_is_attestation'] is False and proof['compile_jobs'] == 1, 'Fresh controlled native build required')
    require(proof['sources'] == lock['sources'], 'Controlled source closure differs')
    require(set(q['artifacts']) == NATIVE | PAYLOAD | feed_names(q), 'Native/feed artifact inventory differs')
    check_feed_qualification(q['feed'])
    canonical = q['default']
    require(canonical['independent_builds_identical'] is True and canonical['hardware_tested'] is False, 'Two canonical builds required')
    require(canonical['default_sha256'] == p['default_sha256'] and canonical['default_bytes'] == p['default_bytes']
            and canonical['manifest_sha256'] == p['default_manifest_sha256'], 'Canonical default differs')
    require(q.get('serial_files') == package.serial_files_product.contract(p['product']), 'Native serial admission differs')
    baseline = q['baseline_contract']
    require(baseline == package.baseline_contract(p), 'Released baseline contract differs')
    for key, sanitized in [('admission', False), ('admission_sanitized', True)]:
        row = q[key]
        require(row['elf_count'] == 43 and row['sanitized'] is sanitized
                and row['hardware_calls'] == 0 and row['storage_calls'] == 0 and row['target_instructions_executed'] is False,
                'Complete production-loader admission required: ' + key)
        require(row['mode'] == 'factory-bootstrap-self-admission' and row['active_platform_count'] == row['candidate_platform_count'] == 22 and row['selected_platform_capacity'] == 32, 'Factory graph capacity differs')
        require(row['selected_native_features'] == {'usb_phy': True, 'diagnostic_source': False}, 'Unexpected native optional feature selection')
        transition=row['placement_transition'];negative=row['unauthorized_namespace_control']
        require(transition['prepared'] and transition['cohort_validated'] and transition['elf_count']==43, 'Placement transition admission differs')
        require(negative['expected_rejection'] and not negative['cohort_validated'] and negative['elf_count']==0 and
                negative['control_packaged'] is False,'Unauthorized namespace control missing')
    provisioning = q['provisioning']
    require(provisioning['hardware_tested'] is False and provisioning['compiled_runtime_rows'] > 0 and
            set(provisioning['flags']) == {'RISC_NATIVE_PACKAGE_VOLUME=1', 'RISC_NATIVE_PROVISION_REQUEST=1', 'RISC_PLATFORM_CAPACITY=32'}, 'Native provisioning compilation missing')
    linked = provisioning['linked_layout']; types = linked['types']
    require(types['platform_slots'] == 32 and types['platform_entry_bytes'] == 120 and types['runtime_bytes'] > 0 and
            types['package_workspace_bytes'] == 15208, 'Linked provisioning types differ')
    workspaces = linked['static_workspaces']
    require(set(workspaces) == {'boot_view', 'serial_workspace'} and
            workspaces['boot_view']['bytes'] == 288 and workspaces['serial_workspace']['bytes'] == 2792 and
            all(row['section'] == '.ext_ram.bss' and row['address'] > 0 for row in workspaces.values()), 'Retained workspace placement differs')
    require(linked['package_workspace_allocation'] == 'MALLOC_CAP_INTERNAL|MALLOC_CAP_8BIT', 'Package workspace memory selection differs')
    for key in ('arduino_core_linked', 'ordinary_app_payloads_rebuilt', 'unselected_usb_host_controller'):
        require(q['native'][key] is False, 'Unexpected native composition: ' + key)
    require(q['native']['elf_bin_identical'] is True, 'Native ELF/BIN identity required')
    model = q['preservation_software_model']
    require(model['passed'] is True and model['cases'] == 496 and model['nvs_and_appdata_preserved'] is True
            and model['bootloader_compatibility_tested'] is False and model['hardware_tested'] is False, 'Preservation model differs')
    preservation=q['preservation']
    require(preservation['internal_files']==111 and preservation['internal_elfs']==43 and preservation['internal_apps']==5 and preservation['internal_providers']==38, 'Minimal internal inventory differs')
    require(preservation['external_files']==45 and preservation['external_apps']==22 and len(preservation['moved_elfs'])==21 and preservation['clock_hidden'] and preservation['data_mapping_preserved'], 'External placement differs')
    require(set(preservation['changed_store_files']) <= {'boot.json','cohort.json','clock.json'} | set(p['store_replacements']), 'Replacement scope differs')
    require(q['packing']['empty_blocks']>=4 and q['packing']['independent_round_trip_verified'], 'Final store reserve missing')
    external=q['external_apps']
    require(external['external_app_count']==22 and len(external['apps'])==22 and external['native_elf_sha256']==lock['native_files']['firmware_elf']['sha256'] and external['runtime_commit']==p['runtime_revision'], 'External admission lineage differs')
    require(external['all_required_capabilities_explicitly_granted'] and external['target_instructions_executed'] is False and external['hardware_tested'] is False,'External proof scope differs')
    for app in external['apps']:
        require({t['sanitized'] for t in app['tests']}=={False,True},'External sanitizer matrix missing')
        for test in app['tests']:
            require(test['production_structural_validation'] and test['production_application_admission'] and test['production_removable_image_snapshots']==2 and test['missing_import_rejections']==len(app['imports']) and test['driver_role_rejected'] and test['unsafe_rejected'] and test['malformed_or_truncated_rejections']==4,'Incomplete external admission')
    client=q['historical_springboard_client']
    require(client['passed'] and client['hardware_tested'] is False and client['system_source']=='f31f89636304d202c49884e2e9b2e0b2ec5fb891' and len(client['visible_rows'])==24 and {r['sanitized'] for r in client['results']}=={False,True},'Historical Springboard client proof missing')
    require(client['retained_springboard_elf_sha256']==q['baseline_contract']['files']['springboard.elf']['sha256'] and client['retained_manifest_sha256']==q['baseline_contract']['files']['springboard.json']['sha256'],'Retained Springboard client identity differs')
    nav=q['navigation']
    require(nav['passed'] is True and nav['hardware_tested'] is False and nav['runtime_commit']==p['runtime_revision'],'Production navigation qualification missing')
    require(nav['external_app_count']==22 and nav['visible_catalog_count']==24 and nav['provider_count']==38 and nav['clock_hidden'] and nav['newly_moved_internal_images_absent']==21,'Navigation graph differs')
    require(nav['production_runtime_graph_unchanged'] and nav['production_structural_validation'] and nav['production_serial_per_file_installation'] and nav['target_instructions_executed'] is False,'Navigation proof boundary differs')
    for sanitized in (False,True):
        tests=[t for t in nav['tests'] if t['sanitized']==sanitized]
        modes={t['mode']:t for t in tests if 'mode' in t}
        require(set(modes)=={'normal','no-card','missing','malformed','removed','relocation'},'Navigation failure modes incomplete')
        for mode,t in modes.items():
            require(t['catalog_checks']==2 and t['home_invocations']==53 and t['hidden_shim_returns']==2 and t['preference_checks']>0 and t['prior_invocation_preference_reads']>0 and t['app_data_checks']>0,'Navigation/preference observations incomplete')
            require(t['external_failures_recovered']==(0 if mode=='normal' else 44),'External failure recovery differs')
        installs={t['scenario']:t for t in tests if 'scenario' in t}
        require(set(installs)=={'clean','known-lora'},'Per-file install scenarios incomplete')
        for scenario,t in installs.items():
            require(t['production_serial_protocol'] and t['namespace']==12 and t['preserved_sentinels']==5 and t['verified_file_bytes']==6226968 and t['hardware_tested'] is False,'Per-file preservation observations incomplete')
            require((t['create_files'],t['replace_files'],t['verified_prior_hashes'])==((45,45,0) if scenario=='clean' else (42,48,3)),'Explicit create/replace plan differs')
    return lock


def validate_candidate_payloads(root, p, revision, names=None):
    names = names or {}
    path = lambda n: root / names.get(n, n)
    q = decode((path('qualification.json')).read_bytes())
    lock = check_qualification(q, p, revision)
    require(lock == decode((path('source-lock.json')).read_bytes()), 'Candidate source lock differs')
    require((path('source-pins.json')).read_bytes() == (package.DOCS / 'source-pins.json').read_bytes(), 'Recipe pins differ')
    for name in q['artifacts']: require(record((path(name)).read_bytes()) == q['artifacts'][name], 'Native artifact changed: ' + name)
    require(record((path('default.elf')).read_bytes()) == {'bytes': p['default_bytes'], 'sha256': p['default_sha256']}, 'Default ELF changed')
    require(sha((path('default.json')).read_bytes()) == p['default_manifest_sha256'], 'Default manifest changed')
    require(set(lock['native_files']) == native.ARTIFACT_KEYS and set(q['controlled_build']['artifacts']) == native.ARTIFACT_KEYS, 'Incomplete native evidence inventory')
    members = archive_members(path('candidate-evidence.zip'))
    with zipfile.ZipFile(path('candidate-evidence.zip')) as z:
        for name in ('qualification.json', 'default.elf', 'default.json'):
            require(z.read(name) == (path(name)).read_bytes(), 'Evidence differs: ' + name)
        require(decode(z.read('build-evidence/build-closure.json')) == q['controlled_build'], 'Build closure differs')
        require(z.read('build-evidence/source-lock.json') == (path('source-lock.json')).read_bytes(), 'Evidence lock differs')
        for role, row in lock['native_files'].items():
            expected = {k: row[k] for k in ('bytes', 'sha256')}
            require(members.get('build/' + row['path']) == expected
                    and q['controlled_build']['artifacts'][role] == expected, 'Native evidence differs: ' + role)
    for name, role in [('firmware.bin', 'firmware_bin'), ('bootloader.bin', 'bootloader'), ('partitions.bin', 'partitions')]:
        require(q['artifacts'][name] == {k: lock['native_files'][role][k] for k in ('bytes', 'sha256')}, 'Linked payload differs')
    with zipfile.ZipFile(path('sd-apps.zip')) as z:
        require(len(z.namelist())==len(set(z.namelist())),'Duplicate SD inventory')
        inventory={n:record(z.read(n)) for n in z.namelist()}
    require(inventory==q['preservation']['external_files_inventory']==decode(path('sd-inventory.json').read_bytes()),'SD payload digest inventory differs')
    verify_feed_assets(root, q, names)
    return q


def validate_candidate(root, p, revision):
    require((root / 'qualification.json').is_file(), 'Qualification missing')
    q = decode((root / 'qualification.json').read_bytes())
    check_directory(root, expected_names=CANDIDATE | feed_names(q))
    return validate_candidate_payloads(root, p, revision)


def release_names(p, q):
    prefix = PRODUCTS[p['product']][1] + '-' + p['version'] + '-SD-Apps'
    renamed = {'factory-candidate-erases-data-0x0.bin': prefix + '-factory-erases-data-0x0.bin',
               'candidate-evidence.zip': prefix + '-Evidence.zip'}
    names = {renamed.get(n, n) for n in CANDIDATE | feed_names(q)} | {'RELEASE-NOTES.txt', 'TESTING.txt', 'release.json', 'ci-provenance.zip'}
    return names, renamed


CI_FILES = {'ci-run.json', 'workflow.yml', 'baseline-release.json', 'baseline-tag.json', 'compiler-version.txt', 'iq-linked.json'}


def verify_ci_provenance(path, p, revision, native_proof):
    members = archive_members(path)
    require(set(members) == CI_FILES, 'CI provenance inventory differs')
    repo = 'michaelrolphone-cmyk/' + PRODUCTS[p['product']][0]
    with zipfile.ZipFile(path) as z:
        ci = decode(z.read('ci-run.json'))
        require(ci['GITHUB_REPOSITORY'] == repo and ci['GITHUB_SHA'] == revision and ci['GITHUB_WORKFLOW_SHA'] == revision, 'CI source identity differs')
        require(ci['GITHUB_REF'] in ('refs/heads/provision/product-integration-053', 'refs/heads/' + p['release_branch']), 'Unexpected CI source branch')
        require(ci['GITHUB_WORKFLOW_REF'] == repo + '/.github/workflows/minimal-sd-native.yml@' + ci['GITHUB_REF'], 'CI workflow identity differs')
        require(all(re.fullmatch('[1-9][0-9]*', ci[k]) for k in ('GITHUB_RUN_ID', 'GITHUB_RUN_ATTEMPT')), 'CI run identity missing')
        require(z.read('workflow.yml') == (package.ROOT / '.github/workflows/minimal-sd-native.yml').read_bytes(), 'Published workflow snapshot differs')
        c = package.baseline_contract(p); tag = decode(z.read('baseline-tag.json')); baseline = decode(z.read('baseline-release.json'))
        require(tag['ref'] == 'refs/tags/' + c['release_tag'] and tag['object']['type'] == 'commit' and tag['object']['sha'] == c['source_revision'], 'Baseline tag provenance differs')
        require(baseline['tag_name'] == c['release_tag'] and baseline['draft'] is False, 'Baseline release provenance differs')
        assets = [a for a in baseline['assets'] if a['name'] == c['factory_asset']]
        require(len(assets) == 1 and assets[0]['browser_download_url'] == 'https://github.com/' + repo + '/releases/download/' + c['release_tag'] + '/' + c['factory_asset'], 'Baseline asset provenance differs')
        require(b'esp-15.2.0_20251204' in z.read('compiler-version.txt'), 'Compiler provenance differs')
        iq = decode(z.read('iq-linked.json'))
        require(iq == native_proof['radio_iq'], 'CI/qualified IQ proof differs')
        target = decode((package.ROOT / 'docs/native-idf61/released-baseline.json').read_bytes())['target']
        require(iq['schema'] == 1 and iq['target_identity'] == target and re.fullmatch('[0-9a-f]{64}', iq['elf_sha256']), 'Final IQ link qualification missing')
    return {'repository': repo, 'run_id': int(ci['GITHUB_RUN_ID']), 'run_attempt': int(ci['GITHUB_RUN_ATTEMPT']),
            'source_revision': revision, 'firmware_elf_sha256': iq['elf_sha256'], 'workflow_sha256': sha((package.ROOT / '.github/workflows/minimal-sd-native.yml').read_bytes())}


def transport(args):
    p = package.pins(final=True)
    package.clean_source(package.ROOT, args.source_revision)
    q = validate_candidate(args.candidate, p, args.source_revision)
    require(not args.output.exists(), 'Release output must be new')
    # The same-run caller supplies exact clean sources; never load executable
    # Python from candidate ZIPs or accept a detached receipt as an attestation.
    for role in ('runtime', 'image_helper'):
        package.clean_source(getattr(args, role), p[role + '_revision'])
    sys.path[:0] = [str(args.runtime / 'scripts'), str(args.image_helper / 'scripts')]
    from read_only_spiffs import read_image
    from prepare_preserving_update import layout, pair
    baseline = args.baseline.read_bytes()
    c = package.baseline_contract(p)
    require(record(baseline) == {'bytes': c['factory_bytes'], 'sha256': c['factory_sha256']}, 'Released factory differs')
    before = read_image(pair(baseline, 0, layout(baseline))[2], 0x550000)
    package.check_baseline(before, c)
    factory = (args.candidate / 'factory-candidate-erases-data-0x0.bin').read_bytes()
    _, firmware, store = pair(factory, 0, layout(factory))
    require(firmware == (args.candidate / 'firmware.bin').read_bytes() and store == (args.candidate / 'store.bin').read_bytes(), 'Factory pair differs')
    extracted = read_image(store, 0x550000)
    with zipfile.ZipFile(args.candidate/'sd-apps.zip') as archive:
        require(len(archive.namelist())==len(set(archive.namelist())),'Duplicate external member')
        payload={n:archive.read(n) for n in archive.namelist()}
    companion={n:payload[n] for n in c['historical_external_companion']['files']}
    expected,expected_payload,preservation=package.compose(before,companion,{n:extracted[n] for n in p['store_replacements']},p,args.source_revision,firmware)
    require(extracted==expected and payload==expected_payload and preservation==q['preservation'],'Final extraction/placement differs')
    repository, prefix = PRODUCTS[p['product']]
    stem = prefix + '-' + p['version'] + '-SD-Apps'
    _, rename = release_names(p, q)
    files = {rename.get(n, n): (args.candidate / n).read_bytes() for n in (CANDIDATE | feed_names(q)) - {'SHA256SUMS'}}
    notes = (prefix+' '+p['version']+' essential internal apps plus complete SD applications\n\n'
        'Five internal apps: Home, Springboard, Wi-Fi, Settings, and hidden return-to-Home navigation glue.\n'
        'All38 providers remain internal. Twenty-one retained application ELFs move to SD, alongside existing LoRa Messages:45 files,22 apps.\n'
        'Home SHA256 '+p['default_sha256']+'. Bounded mounted-card sleep repair included.\n'
        'Complete111-file/43-ELF internal core feed uses a version-specific immutable URL.\n'
        'Software-qualified; physical first-start, SD application operation and sleep/wake remain to be tested.\n'
        'Factory flashing ERASES existing internal settings and device data. Back up first. No preserving update kit is supplied.\n'
        'Install the canonical catalog create plan in firmware, payload, verification order. Existing destination collisions fail; replacement must be explicitly selected per file.\n'
        'Unrelated SD files and existing app-data are preserved by per-file transfers. Never format media or replace a directory wholesale.\n'
        'Post-install preference save/readback is tested separately from the factory erasure of old internal data.\n'
        'Do not flash firmware/store files independently. External rows may be visible without a card; failed launches must recover Home.\n')
    files['ci-provenance.zip'] = make_archive({n: (args.metadata / n).read_bytes() for n in CI_FILES})
    # Verify the exact same metadata bytes that are included in the public release.
    import tempfile
    with tempfile.TemporaryDirectory() as temp:
        provenance = Path(temp) / 'ci-provenance.zip'; provenance.write_bytes(files['ci-provenance.zip'])
        ci_proof = verify_ci_provenance(provenance, p, args.source_revision, q['native'])
        require(ci_proof['firmware_elf_sha256'] == q['input_lock']['native_files']['firmware_elf']['sha256'], 'CI IQ/firmware ELF binding differs')
    files['RELEASE-NOTES.txt'] = notes.encode()
    files['TESTING.txt'] = (notes + '\nHardware checks:\n'
        '1. Back up device data, then flash the factory image at offset 0x0 only if erasure is acceptable.\n'
        '2. Confirm Home renders natively at the physical display resolution and touch reaches every edge.\n'
        '3. Change a clock preference, reboot, and verify it persists. Check brightness and configuration reads.\n'
        '4. Open and return from installed applications; check application ELF loading and normal platform operation.\n'
        '5. Verify alarms across light/deep sleep and wake, including an existing scheduled alarm.\n'
        '6. Complete first-start Wi-Fi/SNTP/core provisioning; verify repeated restart, missing network and interrupted downloads remain recoverable.\n'
        '7. Use the pinned Runtime scripts/serial_files.py client over an owner-trusted serial port: enumerate namespaces, create, read back, then explicitly replace a test file.\n'
        '8. Check binary and empty files, nested sibling preservation, interrupted writes and AppData isolation. No boot-bank namespace may be writable.\n'
        'Report the device, firmware version, steps, expected and actual result, and serial logs for failures.\n').encode()
    release = dict(schema=1, repository='michaelrolphone-cmyk/' + repository, product=p['product'], version=p['version'],
        source_revision=args.source_revision, release_tag=p['release_tag'], publication_enabled=p['publication_enabled'],
        native_rebuilt=True, hardware_tested=False, device_accessed=False, factory_erases_data=True,
        preserving_update_kit_emitted=False, default_sha256=p['default_sha256'], default_manifest_sha256=p['default_manifest_sha256'],
        changed_store_files=q['preservation']['changed_store_files'], source_lock=q['input_lock'], qualification_sha256=sha(files['qualification.json']),
        final_factory_default_extracted=True, ci=ci_proof, artifacts={n: record(b) for n, b in sorted(files.items())})
    files['release.json'] = encoded(release)
    files['SHA256SUMS'] = ''.join(sha(b) + '  ' + n + '\n' for n, b in sorted(files.items())).encode()
    args.output.mkdir(parents=True)
    for name, data in files.items(): (args.output / name).write_bytes(data)
    verify_output(args.output, sha(files['SHA256SUMS']), args.source_revision)
    print('Same-run native release transport and final factory extraction PASS; hardware not tested')


def verify_output(root, expected_sha, revision):
    p = package.pins(final=True)
    require((root / 'qualification.json').is_file(), 'Qualification missing')
    q = decode((root / 'qualification.json').read_bytes())
    names, renamed = release_names(p, q)
    rows = check_directory(root, expected_sha, names)
    release = decode((root / 'release.json').read_bytes())
    require(release['schema'] == 1 and release['repository'] == 'michaelrolphone-cmyk/' + PRODUCTS[p['product']][0], 'Release repository/schema differs')
    require(set(release['artifacts']) == set(rows) - {'release.json'}, 'Release inventory differs')
    require(release['source_revision'] == revision and release['version'] == p['version'] and release['product'] == p['product']
            and release['release_tag'] == p['release_tag'] and release['publication_enabled'] is p['publication_enabled'], 'Release identity differs')
    for key, value in {'native_rebuilt': True, 'hardware_tested': False, 'device_accessed': False,
                       'factory_erases_data': True, 'preserving_update_kit_emitted': False, 'final_factory_default_extracted': True}.items():
        require(release[key] is value, 'Release limit differs: ' + key)
    require(release['changed_store_files'] == q['preservation']['changed_store_files'] and release['default_sha256'] == p['default_sha256']
            and release['default_manifest_sha256'] == p['default_manifest_sha256'], 'Release scope differs')
    for name, row in release['artifacts'].items(): require(record((root / name).read_bytes()) == row, 'Released bytes changed')
    q = validate_candidate_payloads(root, p, revision, renamed)
    require(release['ci'] == verify_ci_provenance(root / 'ci-provenance.zip', p, revision, q['native']), 'Release CI binding differs')
    require(release['ci']['firmware_elf_sha256'] == q['input_lock']['native_files']['firmware_elf']['sha256'], 'Released CI IQ/firmware binding differs')
    require(release['source_lock'] == q['input_lock'] and release['qualification_sha256'] == sha((root / 'qualification.json').read_bytes()), 'Release qualification binding differs')
    require(sha((root / 'default.elf').read_bytes()) == p['default_sha256'] and sha((root / 'default.json').read_bytes()) == p['default_manifest_sha256'], 'Released default differs')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-revision', required=True)
    parser.add_argument('--verify', type=Path)
    parser.add_argument('--expected-sha')
    for name in ('candidate', 'runtime', 'image-helper', 'baseline', 'output', 'metadata'): parser.add_argument('--' + name, type=Path)
    args = parser.parse_args()
    require(__debug__, 'Validation cannot be disabled')
    if args.verify:
        require(args.expected_sha is not None, 'Expected checksum custody required')
        verify_output(args.verify, args.expected_sha, args.source_revision)
    else:
        require(all(getattr(args, n) is not None for n in ('candidate', 'runtime', 'image_helper', 'baseline', 'output', 'metadata')), 'Complete same-run input set required')
        transport(args)
