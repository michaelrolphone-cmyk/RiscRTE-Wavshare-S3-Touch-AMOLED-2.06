#!/usr/bin/env python3
"""Native Wi-Fi footer correction over the exact released 0.1.54 store."""
import argparse
import copy
import importlib.util
import json
from pathlib import Path
import re
import sys

import serial_files_product as serial_files

from package_alarm_sleep import encoded, record, require, sha, clean_source

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / 'docs/wifi-footer'
CHANGED = ['cohort.json', 'wifi_settings.elf', 'wifi_settings.json']
ALARM_SHA = '189ce61b0e4a2b08cbd83ff90564a4c79a6c5e9a3d74b4ad4dcc2a61b4b51604'


def pins():
    p = json.loads((DOCS / 'source-pins.json').read_bytes())
    require(p['schema'] == 1 and p['product'] in ('twatch', 'waveshare'), 'Invalid product contract')
    require(type(p['finalized']) is bool and type(p['publication_enabled']) is bool, 'Invalid publication gates')
    require(p['changed_store_files'] == CHANGED and p['alarm_sha256'] == ALARM_SHA, 'Unexpected change scope')
    require(p['release_tag'] == 'test-wifi-footer-' + p['version'], 'Wrong release tag')
    require(p['release_branch'] == 'release/wifi-footer-' + p['version'], 'Wrong release branch')
    require(sha((DOCS / 'released-baseline.json').read_bytes()) == p['baseline_contract_sha256'], 'Released baseline contract changed')
    for path, expected in p['historical_contracts'].items():
        require(sha((ROOT / path).read_bytes()) == expected, 'Historical contract modified: ' + path)
    for role in ('watch', 'system', 'utilities', 'sdk', 'image_helper', 'wifi_repair'):
        require(re.fullmatch('[0-9a-f]{40}', p[role + '_revision']), 'Immutable source pin required: ' + role)
    if p['finalized'] or p['publication_enabled']:
        require(p['finalized'] and re.fullmatch('[0-9a-f]{40}', p.get('runtime_revision') or ''), 'Final Runtime pin required')
    require(p['serial_files'] == serial_files.check_profile((ROOT / 'profiles/native-idf61.cmake').read_text(), p['product'],
        (ROOT / p['previous_release_profile']).read_text()), 'Serial product authority differs')
    for path, expected in p['native_input_sha256'].items():
        require(sha((ROOT / path).read_bytes()) == expected, 'Native product input differs: ' + path)
    require(sha((ROOT/'drivers/power_axp2101/driver.c').read_bytes()) == p['power_provider']['source_sha256'], 'Power source differs')
    require(sha((ROOT/'drivers/power_axp2101/manifest.json').read_bytes()) == p['power_provider']['manifest_sha256'], 'Power source manifest differs')
    require(sha((DOCS/'power-header-selection.json').read_bytes()) == p['power_provider']['header_selection_sha256'], 'Power header selection differs')
    return p


def baseline_contract(p):
    c = json.loads((DOCS / 'released-baseline.json').read_bytes())
    require(c['product'] == p['product'] and c['version'] == p['baseline_version'], 'Baseline identity differs')
    return c


def check_baseline(before, contract):
    require({n: record(b) for n, b in sorted(before.items())} == contract['files'], 'Released store inventory differs')
    require(sum(n.endswith('.elf') for n in before) == contract['elf_count'], 'Released ELF count differs')
    require(sha(before['alarm-service/driver.elf']) == ALARM_SHA, 'Released alarm fix is missing')
    cohort = json.loads(before['cohort.json'])
    require(cohort['version'] == contract['version'] and cohort['source_revision'] == contract['source_revision'], 'Released cohort differs')


def expected_cohort(before, p, revision, firmware=None):
    require(re.fullmatch('[0-9a-f]{40}', revision), 'Immutable product revision required')
    cohort = dict(json.loads(before['cohort.json']), version=p['version'], source_revision=revision)
    if firmware is not None:
        versions = re.findall(rb'RISC_RUNTIME_VERSION:([^\x00]+)', firmware)
        require(len(versions) == 1, 'Missing/ambiguous Runtime version')
        cohort.update(runtime_version=versions[0].decode('ascii'), firmware_size=len(firmware), firmware_sha256=sha(firmware))
    return cohort


def verify_store(before, after, default, manifest, p, revision, firmware=None, power=None, power_manifest=None, wifi=None, wifi_manifest=None):
    require(set(before) == set(after), 'Store inventory changed')
    require(sorted(n for n in before if before[n] != after[n]) == CHANGED, 'Unexpected changed store files')
    require(record(default) == {'bytes': p['default_bytes'], 'sha256': p['default_sha256']}, 'Retained default ELF differs')
    require(sha(manifest) == p['default_manifest_sha256'], 'Retained default manifest differs')
    require(after['default.elf'] == before['default.elf'] == default and after['default.json'] == before['default.json'] == manifest, 'Common default bytes changed')
    require(after['boot.json'] == before['boot.json'], 'Boot authority changed')
    require(json.loads(after['cohort.json']) == expected_cohort(before, p, revision, firmware), 'Cohort authority changed')
    proof = p['power_provider']
    require(power is not None and power_manifest is not None, 'Exact rebuilt power provider required')
    require(record(power) == {'bytes': proof['elf_bytes'], 'sha256': proof['elf_sha256']}, 'Power provider ELF differs')
    require(sha(power_manifest) == proof['manifest_sha256'], 'Power manifest differs')
    require(after['battery/driver.elf'] == before['battery/driver.elf'] == power and after['battery/manifest.json'] == before['battery/manifest.json'] == power_manifest, 'Retained power provider differs')
    old = json.loads(before['battery/manifest.json']); new = json.loads(power_manifest)
    require(new == old and new['version'] == proof['version'] == '0.1.3', 'Power provider authority changed')
    require(after['alarm-service/driver.elf'] == before['alarm-service/driver.elf'] and sha(after['alarm-service/driver.elf']) == ALARM_SHA, 'Alarm fix changed')
    require(wifi is not None and wifi_manifest is not None, 'Exact rebuilt Wi-Fi required')
    w=p['wifi_package']
    require(record(wifi)==w['elf'] and record(wifi_manifest)==w['manifest'], 'Wi-Fi bytes differ')
    require(after['wifi_settings.elf']==wifi and after['wifi_settings.json']==wifi_manifest, 'Wi-Fi store differs')
    old_wifi=json.loads(before['wifi_settings.json']);new_wifi=json.loads(wifi_manifest)
    require(old_wifi['version']=='1.1.33' and new_wifi==dict(old_wifi,version='1.1.34'), 'Wi-Fi authority changed')
    return {'changed_store_files': CHANGED, 'unchanged_store_payloads': len(before) - len(CHANGED),
            'unchanged_elf_count': sum(n.endswith('.elf') for n in before) - 1,
            'default': record(default), 'default_manifest': record(manifest), 'alarm_sha256': ALARM_SHA,
            'power_provider': record(power), 'power_manifest': record(power_manifest), 'wifi':record(wifi), 'wifi_manifest':record(wifi_manifest)}


def compose(before, default, manifest, p, revision, firmware=None, power=None, power_manifest=None, wifi=None, wifi_manifest=None):
    after = dict(before)
    after.update({'battery/driver.elf': power, 'battery/manifest.json': power_manifest,
                  'cohort.json': encoded(expected_cohort(before, p, revision, firmware)),
                  'wifi_settings.elf':wifi,'wifi_settings.json':wifi_manifest})
    verify_store(before, after, default, manifest, p, revision, firmware, power, power_manifest, wifi, wifi_manifest)
    return after
