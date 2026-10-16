#!/usr/bin/env python3
"""Compose a complete provisioning factory over the immutable released store.

This recipe never weakens the existing update validator or changes historical
release recipes. Namespace6 sharing is a factory policy change, not an approved
preserving transition from0.1.52. Hardware acceptance remains separate.
"""
import copy
import importlib.util
import json
from pathlib import Path
import re
import tempfile

from package_alarm_sleep import encoded, record, require, sha, clean_source
import provisioning_mirrors

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / 'docs/provisioning'
CHANGED = ['boot.json', 'cohort.json', 'default.elf', 'default.json']
ADDED = ['installed-apps/driver.elf', 'installed-apps/manifest.json',
         'pkg-internal/driver.elf', 'pkg-internal/manifest.json']
SETTINGS_SHA = 'a7558b3bd2cd0c2a0edee95e4a8a69477a63772e8300e33e8e7332a2558f8d41'
ALARM_SHA = '189ce61b0e4a2b08cbd83ff90564a4c79a6c5e9a3d74b4ad4dcc2a61b4b51604'


def pins():
    p = json.loads((DOCS / 'source-pins.json').read_bytes())
    require(p['schema'] == 1 and p['product'] == 'waveshare', 'Wrong product')
    require(p['changed_store_files'] == CHANGED and p['added_store_files'] == ADDED, 'Scope changed')
    require(p['release_tag'] == 'test-provisioning-' + p['version'], 'Wrong release tag')
    require(p['release_branch'] == 'release/provisioning-' + p['version'], 'Wrong release branch')
    require(sha((DOCS / 'released-baseline.json').read_bytes()) == p['baseline_contract_sha256'], 'Baseline contract changed')
    for path, digest in p['historical_contracts'].items():
        require(sha((ROOT / path).read_bytes()) == digest, 'Historical contract changed: ' + path)
    for role in ('watch', 'system', 'utilities', 'runtime', 'drivers', 'sdk', 'image_helper'):
        require(re.fullmatch('[0-9a-f]{40}', p[role + '_revision']), 'Immutable source required: ' + role)
    require(p['feed_url'] == 'https://github.com/michaelrolphone-cmyk/RiscRTE-Wavshare-S3-Touch-AMOLED-2.06/releases/download/' + p['release_tag'] + '/native-packages-v1.json', 'Feed destination differs')
    return p


def baseline_contract(p):
    c = json.loads((DOCS / 'released-baseline.json').read_bytes())
    require(c['version'] == p['baseline_version'] and c['elf_count'] == 62, 'Baseline identity differs')
    return c


def check_baseline(before, contract):
    require({n: record(b) for n, b in sorted(before.items())} == contract['files'], 'Released store inventory differs')
    require(len(before) == 128 and sum(n.endswith('.elf') for n in before) == 62, 'Released inventory count differs')
    require(sha(before['settings.elf']) == SETTINGS_SHA, 'Released Settings changed')
    require(sha(before['alarm-service/driver.elf']) == ALARM_SHA, 'Released alarm fix changed')


def provider_inputs(root, p, catalog, compiler=None):
    manifest = (root / 'manifest.json').read_bytes()
    elf = (root / 'driver.elf').read_bytes()
    receipt = json.loads((root / 'build.json').read_bytes())
    require(sha(elf) == receipt['elf_sha256' if catalog else 'sha256'], 'Provider build receipt differs')
    if catalog:
        require(all(receipt.get(key) is True for key in ('boot_profiles', 'native_feed', 'internal_packages')), 'Provider selection incomplete')
        require(receipt['feed_product'] == p['feed_product'] and receipt['feed_url'] == p['feed_url'] and receipt['time_server'] == p['time_server'], 'Provider feed selection differs')
        require({'capability': 'platform.provision-request', 'api': 1} in json.loads(manifest)['requires'], 'Provider request authority missing')
    if catalog:
        import compact_cohort_elf
        require(compiler is not None and sha(elf) == p['catalog_original_sha256'], 'Exact catalog producer required')
        with tempfile.TemporaryDirectory(prefix='wave-catalog-compact-') as directory:
            target = Path(directory) / 'driver.elf'; target.write_bytes(elf)
            compact_cohort_elf.compact(target, compiler, debug_path=Path(directory) / 'original.elf')
            elf = target.read_bytes()
        require(record(elf) == {'bytes': p['catalog_bytes'], 'sha256': p['catalog_sha256']}, 'Packaged catalog differs')
    else:
        require(sha(elf) == p['internal_sha256'], 'Internal adapter differs')
    return elf, manifest


def policy(before, default, store):
    boot = copy.deepcopy(json.loads(before['boot.json']))
    require(boot['installation'] == {'grants': [], 'volume_instance': 12}, 'Baseline installation differs')
    require(len(boot['drivers']) == 36, 'Baseline driver count differs')
    row = next(p for p in boot['app_capabilities'] if p['manifest'] == 'default.json')
    for capability, instance in [('software.installed-apps', 0), ('storage.key-value', 6), ('storage.volume', 12)]:
        grant = {'capability': capability, 'api': 1, 'instance_id': instance}
        require(grant not in row['grants'], 'New Home authority already present')
        row['grants'].append(grant)
    manifest = json.loads(default)
    declared = {(r['capability'], r['api']) for r in manifest['requires'] + manifest.get('optional', [])}
    require(all((g['capability'], g['api']) in declared for g in row['grants']), 'Home grant is undeclared')
    usb = next(d for d in boot['drivers'] if d['manifest'] == 'usb-msc/manifest.json')
    require(set(usb) == {'manifest'}, 'Baseline USB policy differs')
    usb['bindings'] = [{'capability': 'storage.volume', 'api': 1, 'instance_id': 12}]
    boot['drivers'] += [
        {'manifest': 'installed-apps/manifest.json', 'app_data': [{'name': 'installed.apps', 'namespace': 2000, 'access': 'read-write'}]},
        {'manifest': 'pkg-internal/manifest.json'}]
    envelope = [{'capability': c, 'api': api, 'instance_id': instance} for c, api, instance in [
        ('display.output', 1, 5), ('input.touch.raw', 1, 6), ('board.battery', 1, 4),
        ('alarm.service', 1, 0), ('storage.volume', 1, 12), ('runtime.realtime', 1, 0),
        ('storage.key-value', 1, 0), ('storage.app-data', 1, 0)]]
    boot['installation'].update(internal_volume_instance=0, namespace_range={'first': 3000, 'count': 128},
        grants=envelope, provider_grants=[g for g in envelope if g['capability'] not in ('storage.key-value', 'storage.app-data')])
    with tempfile.TemporaryDirectory(prefix='wave-provision-policy-') as directory:
        root = Path(directory)
        for name, data in store.items():
            path = root / name; path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(data)
        mirrors = provisioning_mirrors.compose(boot, root, 'wave', [])
    return boot, mirrors


def expected_cohort(before, p, revision, firmware=None):
    require(re.fullmatch('[0-9a-f]{40}', revision), 'Immutable product revision required')
    cohort = dict(json.loads(before['cohort.json']), version=p['version'], source_revision=revision)
    if firmware is not None:
        versions = {v for v in re.findall(rb'RISC_RUNTIME_VERSION:([^\x00]*)\x00', firmware) if v}
        require(len(versions) == 1, 'Native version identity ambiguous')
        cohort.update(runtime_version=versions.pop().decode('ascii'), firmware_size=len(firmware), firmware_sha256=sha(firmware))
    return cohort


def compose(before, default, manifest, providers, p, revision, firmware=None):
    require(record(default) == {'bytes': p['default_bytes'], 'sha256': p['default_sha256']} and sha(manifest) == p['default_manifest_sha256'], 'Canonical Home differs')
    require(set(providers) == set(ADDED), 'New providers incomplete')
    after = dict(before, **providers)
    after.update({'default.elf': default, 'default.json': manifest})
    boot, mirrors = policy(before, manifest, after)
    after['boot.json'] = (json.dumps(boot, separators=(',', ':'), sort_keys=True) + '\n').encode()
    after['cohort.json'] = encoded(expected_cohort(before, p, revision, firmware))
    verify_store(before, after, default, manifest, providers, p, revision, firmware)
    return after, mirrors


def verify_store(before, after, default, manifest, providers, p, revision, firmware=None):
    require(set(after) - set(before) == set(ADDED) and not set(before) - set(after), 'Inventory changed beyond new providers')
    changed = sorted(n for n in before if before[n] != after[n])
    require(changed == CHANGED, 'Unapproved replacement: ' + repr(changed))
    require(after['default.elf'] == default and after['default.json'] == manifest, 'Home payload changed')
    require(all(after[n] == providers[n] for n in ADDED), 'Provider payload changed')
    require(record(default) == {'bytes': p['default_bytes'], 'sha256': p['default_sha256']} and sha(manifest) == p['default_manifest_sha256'], 'Canonical Home identity differs')
    require(json.loads(after['boot.json']) == policy(before, manifest, after)[0], 'Product policy changed')
    require(json.loads(after['cohort.json']) == expected_cohort(before, p, revision, firmware), 'Cohort differs')
    require(sha(after['settings.elf']) == SETTINGS_SHA and after['settings.elf'] == before['settings.elf'], 'Settings replaced')
    require(sha(after['alarm-service/driver.elf']) == ALARM_SHA, 'Alarm fix replaced')
    require(len(after) == 132 and sum(n.endswith('.elf') for n in after) == 64, 'Incomplete store')
    return {'changed_store_files': changed, 'added_store_files': ADDED, 'unchanged_store_payloads': 124,
        'unchanged_elf_count': 61, 'elf_count': 64, 'file_count': 132, 'settings_sha256': SETTINGS_SHA,
        'alarm_sha256': ALARM_SHA, 'old_to_new_preserving_update_authorized': False}
