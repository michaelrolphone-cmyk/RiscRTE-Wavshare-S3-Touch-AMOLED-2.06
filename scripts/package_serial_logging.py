#!/usr/bin/env python3
"""Exact .61-to-.62 recovery composition, retaining the released app placement."""
import copy
import json
from pathlib import Path
import re
import zipfile

from package_minimal_sd import ROOT, CORE, require, sha, record, encoded, external_path, write_tree
import serial_files_product

DOCS = ROOT / 'docs/serial-logging-recovery'
REPLACEMENTS = {'installed-apps/driver.elf'}


def baseline_contract(p=None):
    c = json.loads((DOCS / 'baseline-0.1.62.json').read_bytes())
    c.update(factory_bytes=c['factory']['bytes'], factory_sha256=c['factory']['sha256'],
             store_sha256=c['store']['sha256'])
    return c


def pins(final=False):
    p = json.loads((DOCS / 'source-pins.json').read_bytes())
    require(p['schema'] == 1 and p['product'] == 'waveshare' and p['version'] == '0.1.63', 'Product/version differs')
    require(p['release_tag'] == 'test-sd-apps-' + p['version'] and
            p['release_branch'] == 'release/sd-apps-' + p['version'], 'Release destination differs')
    require(p['feed_url'].endswith('/provisioning-index/' + p['version'] + '/native-packages-v1.json'), 'Core feed must match exact native product version')
    require(p.get('publication_authorized') is True, 'Publication scope missing')
    from consolidated_wave_source import historical_contract, validate
    validate(ROOT)
    for path, digest in p['historical_contracts'].items():
        historical_contract(path, digest)
    for role in ('watch', 'system', 'utilities', 'drivers', 'sdk', 'image_helper'):
        require(re.fullmatch('[0-9a-f]{40}', p[role + '_revision']), 'Exact source revision missing: ' + role)
    if final:
        require(p['finalized'] is True and re.fullmatch('[0-9a-f]{40}', p.get('runtime_revision') or ''), 'Qualified Runtime pin required')
        require(p['serial_logging']['status'] == 'components-qualified-native-product-pending', 'Runtime component qualification missing')
        require(set(p['store_replacements']) == REPLACEMENTS, 'Versioned catalog replacement locks missing')
    return p


def check_baseline(before, contract):
    require({n: record(b) for n, b in sorted(before.items())} == contract['files'], 'Public .61 inventory differs')
    require(len(before) == 111 and sum(n.endswith('.elf') for n in before) == 43, 'Baseline count differs')
    boot = json.loads(before['boot.json'])
    require(len(boot['drivers']) == 38 and len(boot['app_capabilities']) == 27, 'Baseline graph differs')
    require(sorted(contract['core_manifest_paths']) == list(CORE), 'Essential inventory differs')
    require(json.loads(before['clock.json'])['launcher_visible'] is False, 'Navigation shim must remain hidden')
    require(not any('image_source' in d for d in boot['drivers']), 'Provider moved externally')
    for row in boot['app_capabilities']:
        app = contract['applications'][row['manifest']]
        if row['manifest'] in CORE:
            require('image_source' not in row and app['elf'] in before, 'Essential app not internal')
        else:
            require(row['image_source'] == {'volume_instance': 12, 'path': app['image_path']} and
                    app['elf'] not in before, 'External app policy changed')
    return boot


def companion_files(path, contract):
    raw = Path(path).read_bytes()
    require(record(raw) == contract['external_archive'], 'Public .61 SD archive differs')
    with zipfile.ZipFile(path) as archive:
        require(len(archive.namelist()) == len(set(archive.namelist())), 'Duplicate SD paths')
        files = {n: archive.read(n) for n in archive.namelist()}
    require({n: record(b) for n, b in sorted(files.items())} == contract['external_files'], 'Public .61 SD inventory differs')
    return files


def compose(before, companion, replacements, p, revision, firmware=None, contract=None):
    contract = baseline_contract() if contract is None else contract
    check_baseline(before, contract)
    require(re.fullmatch('[0-9a-f]{40}', revision), 'Exact product revision required')
    require(set(replacements) == set(p.get('store_replacements', {})) <= REPLACEMENTS, 'Replacement scope differs')
    require(all(record(data) == p['store_replacements'][name] for name, data in replacements.items()), 'Replacement digest differs')
    require({n: record(b) for n, b in sorted(companion.items())} == contract['external_files'], 'Public .61 SD inventory differs')
    require(len(companion) == 45 and sum(n.endswith('.elf') for n in companion) == 22, 'External count differs')
    for name in companion:
        external_path(name)
    after = dict(before, **replacements)
    cohort = dict(json.loads(before['cohort.json']), version=p['version'], source_revision=revision)
    if firmware is not None:
        versions = {v for v in re.findall(rb'RISC_RUNTIME_VERSION:([^\x00]*)\x00', firmware) if v}
        require(len(versions) == 1, 'Native version identity ambiguous')
        cohort.update(runtime_version=versions.pop().decode('ascii'), firmware_size=len(firmware), firmware_sha256=sha(firmware))
    after['cohort.json'] = encoded(cohort)
    changed = sorted(n for n in after if after[n] != before[n])
    require(set(after) == set(before) and set(changed) <= {'cohort.json'} | REPLACEMENTS, 'Unapproved retained payload change')
    require(after['boot.json'] == before['boot.json'], 'Boot policy/grants/data mapping changed')
    payload = dict(companion)
    return after, payload, dict(schema=1, internal_files=111, internal_elfs=43, internal_apps=5,
        internal_providers=38, external_files=45, external_apps=22, moved_elfs=[],
        changed_store_files=changed, retained_files=len(after)-len(changed), clock_hidden=True,
        data_mapping_preserved=True, external_files_inventory={n: record(b) for n, b in sorted(payload.items())},
        external_bytes=sum(map(len, payload.values())), external_max_file_bytes=max(map(len, payload.values())),
        external_payload_byte_identical=True, all_other_packaged_assets_retained=True,
        factory_erases_internal_data=True, hardware_tested=False, target_instructions_executed=False)
