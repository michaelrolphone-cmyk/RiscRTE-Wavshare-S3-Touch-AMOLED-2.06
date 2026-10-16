#!/usr/bin/env python3
"""Reproduce the delivered Wave storage/admission audit. Never emits an installer.

Verify the complete firmware-owned boot store and separately published LoRa
companion. The existing internal policy consumes the external ELF through the
explicit namespace12 provider binding; no application is moved by this audit.
"""
import argparse
import hashlib
import io
import zipfile
import json
from pathlib import Path
import subprocess
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / 'docs/catalog-payload/admission-0.1.52/baseline.json'


def require(ok, message):
    if not ok:
        raise ValueError(message)


def encoded(value):
    return (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False) + '\n').encode()


def record(data):
    return {'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}


def exact(data, expected, label):
    require(record(data) == expected, 'Exact bytes differ: ' + label)
    return data


def check_external_sources(boot, contract):
    external = [row for row in boot['app_capabilities'] if 'image_source' in row]
    require(external == contract['external_app_policies'], 'External executable inventory differs')
    require(not any('image_source' in row for row in boot['drivers']),
            'Storage dependency closure is no longer entirely internal')
    return external


def classify(files, contract):
    require({n: record(b) for n, b in sorted(files.items())} == contract['store_files'],
            'Complete released store inventory differs')
    boot = json.loads(files['boot.json'])
    require(boot['default_app'] == 'default.elf', 'Default boot path changed')
    external = check_external_sources(boot, contract)
    require(boot['installation'] == {'volume_instance': 12, 'grants': []},
            'Installation authority changed')
    require(len(boot['app_capabilities']) == 27 and len(boot['drivers']) == 36,
            'Boot composition changed')
    default = next(r for r in boot['app_capabilities'] if r['manifest'] == 'default.json')
    route = [g for g in default['grants'] if g['capability'] == 'storage.files']
    require(route == [{'api': 1, 'backend_capability': 'storage.volume', 'backend_instance': 12,
                      'backend_provider': 'sdmmc-fatfs', 'capability': 'storage.files',
                      'instance_id': 12, 'label': 'SD card'}], 'Default file authority differs')
    drivers = [r for r in boot['drivers'] if r.get('instance_id') == 12]
    require(drivers == [{'instance_id': 12, 'manifest': 'sd-volume/manifest.json'}],
            'Serial consumer provider is ambiguous')
    driver = json.loads(files['sd-volume/manifest.json'])
    require(driver['id'] == 'sdmmc-fatfs' and
            driver['provides'] == [{'capability': 'storage.volume', 'api': 1}],
            'Selected provider identity differs')
    missing = []
    for name, raw in files.items():
        if not name.endswith('.json'):
            continue
        obj = json.loads(raw)
        if obj.get('type') in ('application', 'driver'):
            target = str(Path(name).parent / obj['file_name'])
            if target not in files:
                missing.append(target)
    require(missing == ['lora_messages.elf'], 'Unaccounted executable dependency')
    require(json.loads(files['lora_messages.json']) == contract['internal_lora_manifest'],
            'Internal admission manifest differs')
    require(contract['candidate_version'] is None and contract['publication_enabled'] is False,
            'Audit must not reserve or publish a candidate')
    return {
        'file_count': len(files), 'bytes': sum(len(b) for b in files.values()),
        'elf_count': sum(n.endswith('.elf') for n in files),
        'json_count': sum(n.endswith('.json') for n in files),
        'ownership': 'firmware-owned boot-store contents',
        'externally_sourced_executables': external,
        'internal_missing_elf_resolved_by_external_policy': missing,
    }


def companion_files(contract, assets, firmware_files):
    companion = contract['companion']
    require(set(assets) == set(companion['assets']), 'Companion artifact set differs')
    for name, expected in companion['assets'].items():
        exact(assets[name], expected, name)
    with zipfile.ZipFile(io.BytesIO(assets['Waveshare-LoRa-0.1.17-SD-card.zip'])) as z:
        names = z.namelist()
        require(len(names) == len(set(names)) and set(names) == set(companion['files']),
                'Complete companion inventory differs')
        files = {name: exact(z.read(name), companion['files'][name], name) for name in names}
    release = json.loads(assets['release.json'])
    require(release['source_revision'] == companion['source_revision'] and
            release['release_tag'] == companion['release_tag'] and
            release['elf_sha256'] == companion['files'][ELF]['sha256'] and
            release['qualification']['files'] == companion['files'], 'Companion provenance differs')
    internal = json.loads(firmware_files['lora_messages.json'])
    external = json.loads(files['Apps/lora_messages/manifest.json'])
    require(internal['version'] == '0.1.16' and external.pop('version') == '0.1.17',
            'Unexpected LoRa package lineage')
    internal.pop('version')
    require(internal == external, 'External metadata changes internal admission authority')
    card = json.loads(files['suite-card.json'])
    require(card['apps'] == [{'image': ELF, 'manifest': 'Apps/lora_messages/manifest.json',
                              'sha256': companion['files'][ELF]['sha256']}],
            'Companion index does not cover the exact ELF')
    return files


ELF = 'Apps/lora_messages/lora_messages.elf'


def payload_inputs(contract, operation):
    """Schema-shaped payload; incomplete product/install identity is never fabricated."""
    require(operation in ('create', 'replace'), 'Explicit per-file operation required')
    fid = contract['release_tag']
    # store.bin is the exact asset containing boot.json and the internal manifest;
    # the audit extracts and checks both, rather than relying on a package label.
    evidence = {'url': 'https://github.com/' + contract['repository'] + '/releases/download/' +
                contract['release_tag'] + '/store.bin',
                'sha256': contract['assets']['store.bin']['sha256']}
    binding = {'url': 'https://github.com/michaelrolphone-cmyk/RiscRTE/blob/' +
               contract['runtime_revision'] + '/src/main.cpp',
               'sha256': next(r['sha256'] for r in contract['source_evidence']
                              if r['role'] == 'runtime' and r['path'] == 'src/main.cpp')}
    payload = {'id': 'waveshare-lora-0.1.17', 'owner': 'waveshare-lora-companion',
        'volumes': [{'id': 'application-content', 'consumer': {'id': 'lora_messages',
            'firmware_id': fid, 'evidence': evidence}, 'requirements': {
                'case_semantics': 'ascii-insensitive', 'hierarchical': True,
                'operations': ['stat', 'get', 'mkdir', operation], 'path_encoding': 'utf-8-exact'}}],
        'bindings': [{'firmware_id': fid, 'volume': 'application-content',
                      'namespace_id': '12', 'evidence': binding}],
        'directories': [{'volume': 'application-content', 'path': p, 'operation': 'ensure-directory'}
                        for p in ('/Apps', '/Apps/lora_messages')],
        'files': [{'volume': 'application-content', 'destination': '/' + n,
                   'source': 'payload/' + n, 'operation': operation,
                   'owner': 'waveshare-lora-companion', 'previous': None, **r}
                  for n, r in sorted(contract['companion']['files'].items())],
        'totals': {'bytes': sum(r['bytes'] for r in contract['companion']['files'].values()),
                   'file_count': len(contract['companion']['files'])}}
    payload['inventory_sha256'] = hashlib.sha256(encoded(payload)).hexdigest()
    return payload


def source_bytes(contract, sources):
    checked = {}
    for row in contract['source_evidence']:
        root = sources.get(row['role'])
        require(root is not None, 'Missing source repository: ' + row['role'])
        # Read the exact immutable Git object, independent of checkout state.
        raw = subprocess.check_output(['git', '-C', str(root), 'show',
                                       row['revision'] + ':' + row['path']])
        require(hashlib.sha256(raw).hexdigest() == row['sha256'], 'Pinned source differs')
        checked[(row['role'], row['path'])] = raw
    return checked


def verify_schema(schema):
    payload = schema['properties']['payload']['properties']
    require(payload['volumes']['minItems'] == 1 and payload['files']['minItems'] == 1 and
            payload['totals']['properties']['file_count']['minimum'] == 1,
            'Frozen nonempty payload contract changed')


def audit(contract, assets, companion_assets, source):
    require(set(assets) == set(contract['assets']), 'Required release artifact set differs')
    for name, expected in contract['assets'].items():
        exact(assets[name], expected, name)
    release = json.loads(assets['release.json'])
    require(release['source_revision'] == contract['source_revision'] and
            release['version'] == contract['version'] and
            release['release_tag'] == contract['release_tag'], 'Released source identity differs')
    pins = json.loads(assets['source-pins.json'])
    require(pins['runtime_revision'] == contract['runtime_revision'], 'Runtime lineage differs')
    factory_name = 'Waveshare-0.1.52-Shared-Default-factory-erases-data-0x0.bin'
    factory = assets[factory_name]
    require(factory[0x2f0000:0x840000] == assets['store.bin'], 'Factory/store extraction differs')
    require(record(factory[0x10000:0x10000 + release['artifacts']['firmware.bin']['bytes']]) ==
            release['artifacts']['firmware.bin'], 'Factory/native extraction differs')
    namespace = {'__name__': 'pinned_read_only_spiffs'}
    helper = source[('image_helper', 'scripts/read_only_spiffs.py')]
    exec(compile(helper, 'pinned_read_only_spiffs.py', 'exec'), namespace)
    files = namespace['read_image'](assets['store.bin'], 0x550000)
    inventory = classify(files, contract)
    companion = companion_files(contract, companion_assets, files)
    require(files['default.elf'] == assets['default.elf'] and
            files['default.json'] == assets['default.json'], 'Shared default extraction differs')
    verify_schema(json.loads(source[('schema', 'docs/catalog-payload/1.0.0/manifest.schema.json')]))
    return {
        'schema': 1, 'audit_status': 'passed',
        'candidate_status': 'inventory-qualified-installer-profile-input-pending',
        'product': contract['product'], 'baseline_version': contract['version'],
        'source_revision': contract['source_revision'],
        'runtime_revision': contract['runtime_revision'],
        'upstream_release_id': contract['upstream_release_id'],
        'firmware_store': inventory,
        'associated_external_payload': {'status': 'verified-existing-companion',
            'files': {n: record(b) for n, b in sorted(companion.items())},
            'runtime_consumed_files': [ELF],
            'distribution_metadata_files': ['Apps/lora_messages/manifest.json', 'suite-card.json'],
            'authority': 'internal lora_messages.json and boot app_capabilities'},
        'missing_builder_inputs': ['supported method_id for declared catalog full factory flash',
            'exact accepted hardware revision and trusted namespace12 profile bounds',
            'trusted manifest/container association with the selected catalog revision'],
        'serial_admission': [
            {'namespace_id': '2', 'writable': True, 'role': 'isolated private serial workspace',
             'required_incoming_payload_consumer_proved': False},
            {'namespace_id': '12', 'writable': True,
             'role': 'explicit product file-volume binding; existing external LoRa executable',
             'required_incoming_payload_consumer_proved': True}],
        'flash': {'method': 'existing full initial factory image', 'offset': 0,
                  'internal_saved_data': 'erased', 'settings': 'erased',
                  'external_volume_physical_test': 'not_performed',
                  'preserving_update_kit': False,
                  'paired_transfer_order': ['firmware', 'payload', 'verify'],
                  'external_volume_effect': 'unknown; payload transferred after flash'},
        'app_image_source': {'selected_by_delivered_product': True,
                             'internal_application_fallback_supported': False,
                             'migration_selected': False},
        'source_evidence': contract['source_evidence'],
        'candidate_version_reserved': False, 'product_release_published': False,
        'hardware_tested': False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--assets', type=Path, required=True)
    parser.add_argument('--companion-assets', type=Path, required=True)
    parser.add_argument('--source', action='append', default=[], metavar='ROLE=REPOSITORY')
    parser.add_argument('--download', action='store_true', help='Fetch exact public baseline assets')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    contract = json.loads(CONTRACT.read_bytes())
    sources = {}
    for item in args.source:
        role, root = item.split('=', 1)
        require(role not in sources, 'Duplicate source role')
        sources[role] = Path(root)
    checked = source_bytes(contract, sources)
    for root, selected in ((args.assets, contract), (args.companion_assets, contract['companion'])):
        if args.download:
            root.mkdir(parents=True, exist_ok=True)
            for name, expected in selected['assets'].items():
                path = root / name
                if path.exists():
                    exact(path.read_bytes(), expected, name)
                    continue
                url = ('https://github.com/' + selected['repository'] + '/releases/download/' +
                       selected['release_tag'] + '/' + name)
                with urllib.request.urlopen(url, timeout=180) as response:
                    raw = response.read(expected['bytes'] + 1)
                path.write_bytes(exact(raw, expected, name))
    assets = {name: (args.assets / name).read_bytes() for name in contract['assets']}
    companion = {name: (args.companion_assets / name).read_bytes() for name in contract['companion']['assets']}
    result = audit(contract, assets, companion, checked)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(encoded(result))
    for operation in ('create', 'replace'):
        args.output.with_name('payload-' + operation + '.json').write_bytes(encoded(payload_inputs(contract, operation)))
    print('Exact firmware and complete existing companion inventory PASS; builder inputs remain explicit.')


if __name__ == '__main__':
    main()
