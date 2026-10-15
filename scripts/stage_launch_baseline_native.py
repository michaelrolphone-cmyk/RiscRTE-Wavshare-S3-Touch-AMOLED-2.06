#!/usr/bin/env python3
"""Stage only exact official native bytes for an app-only successor; no device I/O."""
import argparse
import json
from pathlib import Path
import zipfile
from package_launch_brightness import PINS, encoded, require, sha, verify_baseline_bytes


def verified_native(baseline, evidence):
    verify_baseline_bytes(baseline)
    require(sha(evidence.read_bytes()) == PINS['baseline_evidence_sha256'], 'Official native evidence digest differs')
    with zipfile.ZipFile(evidence) as archive:
        names = archive.namelist()
        require(len(names) == len(set(names)) and archive.testzip() is None, 'Ambiguous or corrupt evidence archive')
        metadata = json.loads(archive.read('release.json'))
        require(metadata['source_revision'] == PINS['baseline_product'] and metadata['runtime_revision'] == PINS['runtime_revision'], 'Official native source differs')
        require(metadata['version'] == PINS['baseline_version'], 'Official native release differs')
        files = {name: archive.read(name) for name in ('firmware.bin', 'firmware.elf')}
        for name, key in (('firmware.bin', 'baseline_native_sha256'), ('firmware.elf', 'baseline_native_elf_sha256')):
            require(sha(files[name]) == PINS[key], 'Official native payload differs: ' + name)
        require(files['firmware.bin'] == baseline[0x10000:0x10000 + len(files['firmware.bin'])], 'Official native payload is not installed baseline firmware')
    files['partitions.bin'] = baseline[0x8000:0x9000]
    receipt = dict(baseline_product=PINS['baseline_product'], runtime_revision=PINS['runtime_revision'],
                   baseline_factory_sha256=PINS['baseline_sha256'], baseline_evidence_sha256=PINS['baseline_evidence_sha256'],
                   native_sha256=sha(files['firmware.bin']), native_elf_sha256=sha(files['firmware.elf']),
                   native_reused_unchanged=True)
    return files, receipt


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('baseline', 'evidence', 'runtime'):
        p.add_argument('--' + name, type=Path, required=True)
    a = p.parse_args()
    files, receipt = verified_native(a.baseline.read_bytes(), a.evidence)
    destination = a.runtime / '.pio/build/waveshare-t051'
    destination.mkdir(parents=True, exist_ok=True)
    files['baseline-native-custody.json'] = encoded(receipt)
    for name, data in files.items():
        target = destination / name
        require(not target.exists() or target.read_bytes() == data, 'Refusing to overwrite different native artifact: ' + name)
        target.write_bytes(data)
    print(json.dumps(receipt, indent=2))


if __name__ == '__main__':
    main()
