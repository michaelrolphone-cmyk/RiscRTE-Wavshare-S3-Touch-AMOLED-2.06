#!/usr/bin/env python3
"""Exact .56-to-.57 placement composition; no device operations or publication."""
import argparse
import copy
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import zipfile

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / 'docs/minimal-sd-apps'
CORE = ('clock.json', 'default.json', 'settings.json', 'springboard.json', 'wifi_settings.json')
REPLACEMENTS = {'default.elf', 'default.json', 'installed-apps/driver.elf',
                'installed-apps/manifest.json', 'sd-volume/driver.elf', 'sd-volume/manifest.json'}


def require(ok, message):
    if not ok:
        raise ValueError(message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def record(data):
    return {'bytes': len(data), 'sha256': sha(data)}


def encoded(value):
    return (json.dumps(value, sort_keys=True, indent=2) + '\n').encode()


def baseline_contract():
    return json.loads((DOCS / 'baseline-0.1.56.json').read_bytes())


def pins(final=False):
    p = json.loads((DOCS / 'source-pins.json').read_bytes())
    require(p['schema'] == 1 and p['product'] == 'waveshare' and p['version'] == '0.1.57', 'Product/version differs')
    require(p['release_tag'] == 'test-sd-apps-' + p['version'] and
            p['release_branch'] == 'release/sd-apps-' + p['version'], 'Release destination differs')
    require(p['feed_url'].endswith('/provisioning-index/' + p['version'] + '/native-packages-v1.json'), 'Feed must be versioned')
    require(p.get('publication_authorized') is True, 'Publication scope missing')
    if final:
        require(p['finalized'] is True and p['mounted_card_repair']['status'] == 'qualified', 'Unqualified component pins')
        require(set(p['store_replacements']) <= REPLACEMENTS and
                {'default.elf', 'installed-apps/driver.elf', 'sd-volume/driver.elf'} <= set(p['store_replacements']), 'Required replacement locks missing')
    for role in ('runtime', 'watch', 'system', 'utilities', 'drivers', 'sdk', 'image_helper'):
        require(re.fullmatch('[0-9a-f]{40}', p[role + '_revision']), 'Exact source revision missing: ' + role)
    return p


def check_baseline(before, contract):
    require({n: record(b) for n, b in sorted(before.items())} == contract['files'], 'Public .56 inventory differs')
    require(len(before) == 132 and sum(n.endswith('.elf') for n in before) == 64, 'Baseline count differs')
    boot = json.loads(before['boot.json'])
    require(len(boot['drivers']) == 38 and len(boot['app_capabilities']) == 27, 'Baseline graph differs')
    require(sorted(contract['core_manifest_paths']) == list(CORE), 'Essential inventory differs')
    return boot


def companion_files(path, contract):
    raw = Path(path).read_bytes()
    expected = contract['historical_external_companion']
    require(record(raw) == expected['archive'], 'Historical external archive differs')
    with zipfile.ZipFile(path) as archive:
        require(len(archive.namelist()) == len(set(archive.namelist())), 'Duplicate companion paths')
        files = {n: archive.read(n) for n in archive.namelist()}
    require({n: record(b) for n, b in files.items()} == expected['files'], 'Historical external inventory differs')
    return files


def external_path(path):
    require(isinstance(path, str) and path.isascii() and path, 'ASCII product path required')
    parts = PurePosixPath(path).parts
    require(parts and str(PurePosixPath(path)) == path and not path.startswith('/') and
            len(path.encode()) <= 511 and not any(p in ('.', '..') or len(p.encode()) > 127 or
            p[-1:] in ('.', ' ') or any(c in p for c in ':\\*?"<>|') for p in parts), 'Invalid external path: ' + path)


def compose(before, companion, replacements, p, revision, firmware=None, contract=None):
    contract = baseline_contract() if contract is None else contract
    boot = copy.deepcopy(check_baseline(before, contract))
    require(re.fullmatch('[0-9a-f]{40}', revision), 'Exact product revision required')
    require(set(replacements) == set(p.get('store_replacements', {})) <= REPLACEMENTS, 'Replacement scope differs')
    require(all(record(data) == p['store_replacements'][name] for name, data in replacements.items()), 'Replacement digest differs')
    require({n: record(b) for n, b in companion.items()} == contract['historical_external_companion']['files'], 'Companion inventory differs')
    after = dict(before, **replacements)
    payload = dict(companion)
    moved = []
    for row in boot['app_capabilities']:
        name = row['manifest']
        app = contract['applications'][name]
        if name in CORE:
            require('image_source' not in row, 'Essential app was external')
            continue
        image_path = app['image_path']; external_path(image_path)
        if app['elf'] in before:
            require(contract['applications_moved_from_internal'] == 21 and 'image_source' not in row, 'Unexpected moved app')
            require(image_path not in payload, 'External path collision')
            payload[image_path] = after.pop(app['elf'])
            manifest_path = str(PurePosixPath(image_path).parent / 'manifest.json')
            require(manifest_path not in payload, 'External manifest collision')
            payload[manifest_path] = before[name]
            row['image_source'] = {'volume_instance': 12, 'path': image_path}
            moved.append(app['elf'])
        else:
            require(row['image_source'] == {'volume_instance': 12, 'path': image_path}, 'Historical external policy changed')
            require(image_path in payload, 'Historical external image missing')
    clock = json.loads(before['clock.json']); clock['launcher_visible'] = False
    after['clock.json'] = encoded(clock)
    after['boot.json'] = encoded(boot)
    cohort = dict(json.loads(before['cohort.json']), version=p['version'], source_revision=revision)
    if firmware is not None:
        versions = {v for v in re.findall(rb'RISC_RUNTIME_VERSION:([^\x00]*)\x00', firmware) if v}
        require(len(versions) == 1, 'Native version identity ambiguous')
        cohort.update(runtime_version=versions.pop().decode('ascii'), firmware_size=len(firmware), firmware_sha256=sha(firmware))
    after['cohort.json'] = encoded(cohort)
    require(len(moved) == 21 and len(after) == 111 and sum(n.endswith('.elf') for n in after) == 43, 'Split inventory differs')
    require(len(payload) == 45 and sum(n.endswith('.elf') for n in payload) == 22, 'Incomplete external payload')
    require(len({p.lower() for p in payload}) == len(payload), 'Case-insensitive payload collision')
    for path in payload:
        external_path(path)
    removed = sorted(set(before) - set(after))
    require(removed == sorted(moved) and not set(after) - set(before), 'Unapproved store removal/addition')
    changed = sorted(n for n in after if before[n] != after[n])
    require(set(changed) <= {'boot.json', 'cohort.json', 'clock.json'} | set(replacements), 'Unapproved replacement')
    require(all(after[n] == before[n] for n in ('settings.elf', 'settings.json', 'wifi_settings.elf', 'wifi_settings.json', 'springboard.elf', 'springboard.json', 'clock.elf')), 'Essential retained payload changed')
    require(boot['drivers'] == json.loads(before['boot.json'])['drivers'], 'Driver policy changed')
    require(not any('image_source' in d for d in boot['drivers']), 'Provider moved externally')
    require(all(after[n] == before[n] for n in before if n.endswith('/driver.elf') and n not in replacements), 'Unapproved provider rebuild')
    for row in boot['app_capabilities']:
        old = next(x for x in json.loads(before['boot.json'])['app_capabilities'] if x['manifest'] == row['manifest'])
        require({k:v for k,v in row.items() if k != 'image_source'} == {k:v for k,v in old.items() if k != 'image_source'}, 'App grant/data mapping changed')
    return after, payload, {'schema':1, 'internal_files':len(after), 'internal_elfs':43, 'internal_apps':5,
        'internal_providers':38, 'external_files':len(payload), 'external_apps':22, 'moved_elfs':removed,
        'changed_store_files':changed, 'retained_files':len(after)-len(changed), 'clock_hidden':True,
        'data_mapping_preserved':True, 'external_files_inventory':{n:record(b) for n,b in sorted(payload.items())},
        'external_bytes':sum(map(len,payload.values())), 'external_max_file_bytes':max(map(len,payload.values())),
        'all_existing_packaged_assets_retained':True, 'factory_erases_internal_data':True,
        'hardware_tested':False, 'target_instructions_executed':False}


def write_tree(root, files):
    require(not root.exists(), 'Output tree must be new')
    root.mkdir(parents=True)
    for name, data in files.items():
        path = root / name; path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(data)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('baseline-store', 'companion', 'replacements', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--source-revision', required=True)
    args = parser.parse_args()
    from read_only_spiffs import read_image
    p = pins(final=True); c = baseline_contract()
    require(record(args.baseline_store.read_bytes()) == c['store'], 'Public store bytes differ')
    before = read_image(args.baseline_store.read_bytes(), 0x550000)
    after, payload, receipt = compose(before, companion_files(args.companion,c),
        {n:(args.replacements/n).read_bytes() for n in p['store_replacements']}, p, args.source_revision)
    write_tree(args.output/'internal',after); write_tree(args.output/'external',payload)
    (args.output/'composition.json').write_bytes(encoded(receipt))
