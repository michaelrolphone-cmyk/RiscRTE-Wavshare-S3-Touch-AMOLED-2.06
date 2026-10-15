#!/usr/bin/env python3
"""Qualify the LoRa brightness companion against the same cumulative firmware release."""
import argparse
import copy
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
import tarfile
import zipfile
from elftools.elf.elffile import ELFFile

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / 'docs/launch-brightness-media'
PINS = json.loads((DOCS / 'source-pins.json').read_bytes())
PRODUCT = 'michaelrolphone-cmyk/RiscRTE-Wavshare-S3-Touch-AMOLED-2.06'
PREFIX = 'Waveshare-0.1.48-LoRa-0.1.18'
ELF = 'Apps/lora_messages/lora_messages.elf'
MANIFEST = 'Apps/lora_messages/manifest.json'
MEMBERS = {ELF, MANIFEST, 'suite-card.json'}
INPUTS = ['scripts/package_launch_brightness_media.py', 'scripts/test_launch_brightness_media.py',
          *['docs/launch-brightness-media/' + name for name in ('README.md', 'INSTALL.txt', 'RELEASE-NOTES.txt',
            'source-pins.json', 'upstream-cohort.json', 'firmware-lora-policy.json', 'firmware-lora-manifest.json')]]


def require(ok, message):
    if not ok:
        raise ValueError(message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def encoded(value):
    return (json.dumps(value, indent=2, sort_keys=True) + '\n').encode()


def run(*args, **kwargs):
    result = subprocess.run([str(x) for x in args], capture_output=True, text=True, **kwargs)
    if result.returncode:
        print(result.stdout + result.stderr, file=sys.stderr)
        raise subprocess.CalledProcessError(result.returncode, args, result.stdout, result.stderr)
    return result.stdout + result.stderr


def sums(files):
    return ''.join(f'{sha(data)}  {name}\n' for name, data in sorted(files.items())).encode()


def archive(path, files, checksums=False):
    files = dict(files)
    if checksums:
        files['SHA256SUMS.txt'] = sums(files)
    with zipfile.ZipFile(path, 'x') as output:
        for name, data in sorted(files.items()):
            require(not PurePosixPath(name).is_absolute() and '..' not in PurePosixPath(name).parts, 'Unsafe archive path')
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            output.writestr(info, data, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    with zipfile.ZipFile(path) as output:
        require(output.testzip() is None and set(output.namelist()) == set(files), 'Archive readback failed')
        require(all(output.read(name) == data for name, data in files.items()), 'Archive content readback failed')


def read_baseline(data):
    require(len(data) == PINS['baseline_bytes'] and sha(data) == PINS['baseline_sha256'], 'Exact official predecessor card required')
    with zipfile.ZipFile(io.BytesIO(data)) as card:
        require(len(card.namelist()) == len(MEMBERS) and set(card.namelist()) == MEMBERS, 'Complete predecessor card member set required')
        require(card.testzip() is None, 'Predecessor ZIP CRC failed')
        return {name: card.read(name) for name in card.namelist()}


def symbols(data):
    image = ELFFile(io.BytesIO(data))
    require(image.elfclass == 32 and image.little_endian and image['e_type'] == 'ET_DYN' and image['e_machine'] == 'EM_XTENSA', 'Expected Xtensa ELF32 shared app')
    table = image.get_section_by_name('.dynsym')
    require(table is not None, 'Dynamic symbol table required')
    return {kind: sorted(s.name for s in table.iter_symbols() if s.name and (s['st_shndx'] == 'SHN_UNDEF') == undefined)
            for kind, undefined in [('imports', True), ('exports', False)]}


def overlay(before, repaired):
    require(set(before) == MEMBERS, 'Unexpected complete card member set')
    require(sha(before[ELF]) == PINS['prior_elf_sha256'] and len(before[ELF]) == PINS['prior_elf_bytes'], 'Predecessor ELF mismatch')
    require(sha(repaired) == PINS['elf_sha256'] and len(repaired) == PINS['elf_bytes'], 'Repair ELF mismatch')
    original = json.loads(before[MANIFEST])
    require(original == dict(json.loads((DOCS / 'firmware-lora-manifest.json').read_bytes()), version=PINS['prior_app_version']), 'External/internal manifest mismatch')
    require(original['version'] == PINS['prior_app_version'], 'Predecessor version mismatch')
    require(original['optional'] == [{'api': 2, 'capability': 'radio.lora'}], 'Optional radio contract changed')
    require(all(r['capability'] != 'radio.lora' for r in original['requires']), 'Radio must remain optional')
    policy = json.loads((DOCS / 'firmware-lora-policy.json').read_bytes())
    require(policy['image_source'] == {'path': ELF, 'volume_instance': 12}, 'External-media route changed')
    require(all(r['capability'] != 'radio.lora' for r in policy['grants']), 'Absent radio must not gain a grant')
    old_marker = b'"version":"0.1.17"'
    require(before[MANIFEST].count(old_marker) == 1, 'Exact version-only manifest marker required')
    manifest = before[MANIFEST].replace(old_marker, b'"version":"0.1.18"')
    require(json.loads(manifest) == dict(original, version=PINS['app_version']), 'Non-version manifest change')
    content = json.loads(before['suite-card.json'])
    require(len(content['apps']) == 1 and content['apps'][0] == {'image': ELF, 'manifest': MANIFEST, 'sha256': PINS['prior_elf_sha256']}, 'Predecessor content digest changed')
    updated = copy.deepcopy(content)
    updated['apps'][0]['sha256'] = PINS['elf_sha256']
    card = dict(before, **{ELF: repaired, MANIFEST: manifest, 'suite-card.json': (json.dumps(updated, separators=(',', ':')) + '\n').encode()})
    require(set(card) == set(before) and all(card[n] != before[n] for n in MEMBERS), 'Card closure changed')
    return card


def isolated(repo, revision, target, names=None):
    require(re.fullmatch('[0-9a-f]{40}', revision), 'Full source revision required')
    data = subprocess.check_output(['git', '-C', str(repo), 'archive', revision, *(['--', *names] if names else [])])
    target.mkdir(parents=True)
    with tarfile.open(fileobj=io.BytesIO(data)) as source:
        require(all(m.isfile() or m.isdir() for m in source), 'Unexpected source archive entry')
        source.extractall(target, filter='data')
    return data


def verify_product_source(revision):
    require(run('git', '-C', ROOT, 'rev-parse', 'HEAD').strip() == revision, 'Product HEAD mismatch')
    require(not run('git', '-C', ROOT, 'diff', 'HEAD', '--name-only').strip(), 'Dirty tracked product source')
    result = {}
    for name in INPUTS:
        data = (ROOT / name).read_bytes()
        require(data == subprocess.check_output(['git', '-C', str(ROOT), 'show', revision + ':' + name]), 'Uncommitted input: ' + name)
        result[name] = sha(data)
    return result


def verify_firmware(factory, metadata, revision, store):
    require(len(factory) == 0x1000000, 'Full firmware factory image required')
    require(metadata['version'] == PINS['firmware_version'] and metadata['source_revision'] == revision, 'Firmware product identity differs')
    require(metadata.get('candidate_sha256', metadata.get('factory_sha256')) == sha(factory), 'Firmware factory digest differs')
    cohort = json.loads(store['cohort.json'])
    require(cohort['version'] == PINS['firmware_version'] and cohort['source_revision'] == revision, 'Factory cohort identity differs')
    require(sha(store['boot.json']) == PINS['firmware_boot_sha256'], 'Existing firmware boot authority changed')
    require(sha(store['lora_messages.json']) == PINS['firmware_lora_manifest_sha256'], 'Existing firmware LoRa admission manifest changed')
    policy = [row for row in json.loads(store['boot.json'])['app_capabilities'] if row['manifest'] == 'lora_messages.json']
    require(policy == [json.loads((DOCS / 'firmware-lora-policy.json').read_bytes())], 'External media route/grants changed')
    return dict(source_revision=revision, version=PINS['firmware_version'], factory_sha256=sha(factory),
                boot_sha256=sha(store['boot.json']), internal_manifest_sha256=sha(store['lora_messages.json']),
                internal_manifest_version=json.loads(store['lora_messages.json'])['version'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('baseline', 'system', 'runtime', 'compiler', 'factory', 'firmware-release', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--source-revision', required=True)
    parser.add_argument('--source-cache', type=Path)
    args = parser.parse_args()
    require(__debug__, 'Python -O is unsupported')
    os.environ['ASAN_OPTIONS'] = 'detect_leaks=0'
    require(not args.output.exists(), 'Fresh output directory required')
    source_files = verify_product_source(args.source_revision)
    require(run('git', '-C', args.runtime, 'rev-parse', 'HEAD').strip() == PINS['runtime_revision'], 'Runtime identity differs')
    sys.path.insert(0, str(args.runtime.resolve() / 'scripts'))
    from spiffs_image import read_image
    factory = args.factory.read_bytes()
    firmware = verify_firmware(factory, json.loads(args.firmware_release.read_bytes()), args.source_revision, read_image(factory[0x2f0000:0x840000], 0x550000))
    upstream_bytes = (DOCS / 'upstream-cohort.json').read_bytes()
    require(sha(upstream_bytes) == PINS['upstream_cohort_sha256'], 'Upstream cohort receipt mismatch')
    upstream = json.loads(upstream_bytes)
    require(sha((DOCS / 'firmware-lora-manifest.json').read_bytes()) == PINS['firmware_lora_manifest_sha256'], 'Firmware manifest changed')
    require(json.loads((DOCS / 'firmware-lora-policy.json').read_bytes()) == upstream['apps']['lora_messages']['original_boot_policy'], 'Firmware boot grants changed')
    before = read_baseline(args.baseline.read_bytes())
    out = args.output.resolve(); out.mkdir(parents=True)
    work = out / 'work'; work.mkdir()
    evidence = {}
    recipe_archive = isolated(args.system, PINS['system_revision'], work / 'recipe', ['scripts/replay_shared_crash_apps.py', 'docs/shared-app-crashes/replay'])
    recipe = work / 'recipe'; replay = work / 'replay'
    command = [sys.executable, recipe / 'scripts/replay_shared_crash_apps.py', '--product', 'wave-media', '--compiler', args.compiler.resolve(), '--output', replay]
    if args.source_cache:
        command += ['--source-cache', args.source_cache.resolve()]
    try:
        evidence['target-replay.log'] = run(*command).encode()
    except subprocess.CalledProcessError:
        for path in replay.rglob('*.log'):
            print(str(path) + '\n' + path.read_text(errors='replace'), file=sys.stderr)
        raise
    receipt = json.loads((replay / 'receipt.json').read_bytes())
    require(receipt['product'] == 'wave-media' and receipt['source_inputs_verified'] and set(receipt['apps']) == {'lora_messages'}, 'Incomplete source replay')
    require(receipt['driver_sha256'] == sha((recipe / 'scripts/replay_shared_crash_apps.py').read_bytes()), 'Replay driver identity changed')
    require(receipt['spec_sha256'] == {p.name: sha(p.read_bytes()) for p in (recipe / 'docs/shared-app-crashes/replay').iterdir() if p.is_file()}, 'Replay spec closure changed')
    require(receipt['compiler'] == PINS['compiler_version'] and receipt['compiler_sha256'] == sha(args.compiler.resolve().read_bytes()), 'Compiler identity changed')
    repaired = (replay / 'lora_messages.elf').read_bytes()
    require(receipt['apps']['lora_messages']['sha256'] == sha(repaired), 'Replay output receipt mismatch')
    require(symbols(before[ELF]) == symbols(repaired) == receipt['apps']['lora_messages']['symbols'], 'Dynamic symbol contract changed')
    caps = upstream['capability_literal_check_universe']
    extract_caps = lambda data: sorted(c for c in caps if (c + '\0').encode() in data)
    require(extract_caps(before[ELF]) == extract_caps(repaired), 'Capability literals changed')
    card = overlay(before, repaired)
    system = replay / 'sources/r0'; utilities = replay / 'sources/r15'
    require(receipt['repositories']['r15']['commit'] == PINS['utilities_revision'], 'LoRa Utilities source changed')
    validator = work / 'validate-elf'
    for sanitized in (False, True):
        extra = ['-fsanitize=address,undefined', '-fno-sanitize-recover=all', '-fno-omit-frame-pointer', '-no-pie'] if sanitized else []
        command = ['cc', '-std=c11', '-Wall', '-Wextra', '-Werror', *extra, '-I' + str(system / 'test/native_apps/stubs'), '-I' + str(system / 'lib/elf_loader/include'), system / 'lib/elf_loader/src/esp_elf_validate.c', system / 'test/native_apps/validate_test.c', '-o', validator]
        evidence[f'elf-validation-{int(sanitized)}.log'] = (run(*command) + run(validator, replay / 'lora_messages.elf')).encode()
    evidence['test_lora_messages.py.log'] = run(sys.executable, utilities / 'scripts/test_lora_messages.py', '--system-apps', system).encode()
    # Retain a paired negative result for the historical, nonselected renderer profile.
    baseline_archive = isolated(args.system, PINS['predecessor_system_revision'], work / 'legacy-predecessor')
    wrapper = work / 'legacy-renderer-cc'
    wrapper.write_text('#!/bin/sh\nexec cc -Wno-missing-field-initializers "$@"\n')
    wrapper.chmod(0o755)
    evidence['legacy-renderer-cc'] = wrapper.read_bytes()
    legacy = {}
    for label, selected_system in [('predecessor', work / 'legacy-predecessor'), ('repaired', system)]:
        command = [sys.executable, utilities / 'scripts/test_lora_renderer.py', '--system-apps', selected_system]
        initial = subprocess.run([str(x) for x in command], capture_output=True, text=True)
        diagnostic = initial.stdout + initial.stderr
        evidence['legacy-renderer-' + label + '-original.log'] = diagnostic.encode()
        errors = [line for line in diagnostic.splitlines() if 'error:' in line]
        require(initial.returncode != 0 and len(errors) == 1 and 'missing initializer for field' in errors[0] and 'confirm_boot' in errors[0],
                'Historical renderer compile diagnosis changed')
        result = subprocess.run([str(x) for x in command], capture_output=True, text=True, env={**os.environ, 'CC': str(wrapper)})
        diagnostic = result.stdout + result.stderr
        evidence['legacy-renderer-' + label + '-compatibility.log'] = diagnostic.encode()
        require(result.returncode != 0 and "radio_sends==1" in diagnostic and '/send-history' in diagnostic,
                'Historical renderer paired failure diagnosis changed')
        legacy[label] = {'system_revision': PINS['predecessor_system_revision'] if label == 'predecessor' else receipt['repositories']['r0']['commit'],
                         'returncode': result.returncode, 'assertion': 'radio_sends==1', 'scenario': 'send-history'}
    profile = {'lora_messages': {'defines': [x for x in json.loads((recipe / 'docs/shared-app-crashes/replay/wave-media.json').read_bytes())['lora_messages']['command'] if x.startswith('-D')]
                 + ['-include', str(replay / 'sources/r3/apps/clock/faces/ContextsFaces.h')]}}
    host_profile = work / 'selected-host-profile.json'; host_profile.write_bytes(encoded(profile))
    shared_output = work / 'shared-input'
    evidence['production-shared-input.log'] = run(sys.executable, utilities / 'scripts/test_lora_shared_input.py',
        '--system-apps', system, '--runtime', replay / 'sources/r1', '--recipe', host_profile,
        '--output', shared_output, '--extra-define', 'PORTABLE_TEXT_INPUT_POLICY').encode()
    shared = json.loads((shared_output / 'qualification.json').read_bytes())
    require(shared['results'] and all(x['returncode'] == 0 for x in shared['results']), 'Production shared-input failure')
    for mode in ('send-history', 'policy-unavailable', 'policy-retained', 'policy-missing-suffix'):
        require({x['sanitized'] for x in shared['results'] if x['mode'] == mode} == {False, True}, 'Missing normal/sanitized production scenario: ' + mode)
    evidence['production-shared-input.json'] = (shared_output / 'qualification.json').read_bytes()
    for path in shared_output.rglob('*.log'):
        evidence['shared-input-logs/' + path.relative_to(shared_output).as_posix()] = path.read_bytes()
    runtime_archive = isolated(args.runtime, PINS['runtime_revision'], work / 'runtime')
    for script in ('run_removable_runtime_test.sh', 'run_optional_app_requirements_test.sh'):
        for sanitized in ('0', '1'):
            evidence[script + '-' + sanitized + '.log'] = run('bash', work / 'runtime/test' / script, env={**os.environ, 'SANITIZE': sanitized, 'ASAN_OPTIONS': 'detect_leaks=0'}).encode()
    evidence['host-package-tests.log'] = run(sys.executable, ROOT / 'scripts/test_launch_brightness_media.py').encode()
    evidence['target-receipt.json'] = (replay / 'receipt.json').read_bytes()
    evidence['source-replay-recipe.tar'] = recipe_archive
    evidence['lora_messages.elf'] = repaired
    for p in replay.rglob('*.log'):
        if p.relative_to(replay).parts[0] not in ('work', 'sources'):
            evidence['replay-logs/' + p.relative_to(replay).as_posix()] = p.read_bytes()
    proof = dict(source_revision=args.source_revision, system_revision=PINS['system_revision'], runtime_revision=PINS['runtime_revision'],
        source_files=source_files, runtime_archive_sha256=sha(runtime_archive), recipe_archive_sha256=sha(recipe_archive),
        source_inputs_verified=True, target_replay_exact=True, structural_validation_normal_sanitized=True,
        symbols=symbols(repaired), capability_literals=extract_caps(repaired), original_boot_policy_preserved=True,
        external_volume_instance=12, external_image_path=ELF, manifest_version_only=True,
        complete_card_members=sorted(card), content_digest_regenerated=True, file_growth_bytes=len(repaired)-len(before[ELF]),
        internal_firmware_assets_modified=False, normal_sanitized_lora_model_shared_input=True,
        production_shared_input_cases=len(shared['results']), normal_sanitized_image_comparisons=shared['normal_sanitized_image_comparisons'],
        inherited_legacy_renderer_failure=legacy, predecessor_archive_sha256=sha(baseline_archive),
        runtime_removable_and_optional_regressions=True, hardware_tested=False,
        app_level_external_media_end_to_end_tested=False, files={n: {'bytes': len(d), 'sha256': sha(d)} for n,d in sorted(card.items())})
    evidence['qualification.json'] = encoded(proof)
    for name in INPUTS:
        evidence['product-source/' + name] = (ROOT / name).read_bytes()
    assets = out / 'assets'; assets.mkdir()
    archive(assets / (PREFIX + '-SD-card.zip'), card)
    archive(assets / (PREFIX + '-evidence.zip'), evidence, checksums=True)
    release = dict(schema='riscrte.external-media-release', schema_version=1, release_tag=PINS['release_tag'],
        version=PINS['app_version'], app_id='lora_messages', source_revision=args.source_revision,
        system_revision=PINS['system_revision'], runtime_revision=PINS['runtime_revision'],
        baseline_tag=PINS['baseline_tag'], baseline_asset=PINS['baseline_asset'], baseline_sha256=PINS['baseline_sha256'],
        firmware_version=PINS['firmware_version'], firmware_tag=PINS['firmware_tag'], firmware_source=args.source_revision,
        firmware_factory_sha256=sha(factory), firmware_unchanged=True, firmware_custody=firmware,
        internal_manifest_version=firmware['internal_manifest_version'], external_manifest_version=PINS['app_version'],
        elf_sha256=sha(repaired), elf_bytes=len(repaired), image_path=ELF, volume_instance=12,
        policy_changes=[], publication_enabled=PINS['publication_enabled'], hardware_tested=False,
        qualification=proof, assets={p.name: {'bytes':p.stat().st_size,'sha256':sha(p.read_bytes())} for p in assets.iterdir()})
    (assets / (PREFIX + '-release.json')).write_bytes(encoded(release))
    for name in ('INSTALL.txt', 'RELEASE-NOTES.txt'):
        (assets / (PREFIX + '-' + name)).write_bytes((DOCS / name).read_bytes())
    (assets / (PREFIX + '-SHA256SUMS.txt')).write_bytes(sums({p.name:p.read_bytes() for p in assets.iterdir()}))
    print(json.dumps({'release_tag':PINS['release_tag'], 'assets':str(assets), 'elf_sha256':sha(repaired), 'passed':True},indent=2))


if __name__ == '__main__':
    main()
