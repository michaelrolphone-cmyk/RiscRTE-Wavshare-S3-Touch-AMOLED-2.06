#!/usr/bin/env python3
"""Compile the production bridge with pinned SDK declarations and test retained I/O.

No SDK drivers are copied or re-declared. Only RTOS scheduling is replaced for the
host model. Target checks reuse the Runtime's configured Xtensa compile command,
one object at a time; no firmware build or device access occurs.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--idf', type=Path, default=ROOT.parent / 'esp-idf')
p.add_argument('--compile-commands', type=Path, default=ROOT.parent / 'runtime/idf/build/compile_commands.json')
p.add_argument('--vendor', type=Path)
p.add_argument('--output', type=Path)
p.add_argument('--sanitize', action='store_true')
group = p.add_mutually_exclusive_group()
group.add_argument('--host-only', action='store_true')
group.add_argument('--target-only', action='store_true')
a = p.parse_args()
provenance = json.loads((ROOT / 'native/vendor-idf6-provenance.json').read_text())
revision = subprocess.check_output(['git', '-C', str(a.idf), 'rev-parse', 'HEAD'], text=True).strip()
if revision != provenance['idf_revision']:
    raise RuntimeError('The SDK revision differs from the audited native bridge')
entry = next(e for e in json.loads(a.compile_commands.read_text()) if e['file'].endswith('/NativeHardware.cpp'))
base = entry.get('arguments') or shlex.split(entry['command'])
includes = [v for v in base if v.startswith('-I') and '/esp_libc/' not in v and '/newlib/' not in v]
if not any(str(a.idf.resolve()) in v for v in includes):
    raise RuntimeError('Compile commands do not reference the selected actual SDK')
owned = tempfile.TemporaryDirectory(prefix='co5300-idf6-') if not a.output else None
out = a.output.resolve() if a.output else Path(owned.name)
out.mkdir(parents=True, exist_ok=True)

def run(command, label, cwd=ROOT):
    (out / (label + '.command.json')).write_text(json.dumps(command, indent=2) + '\n')
    result = subprocess.run(command, cwd=cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    (out / (label + '.log')).write_text(result.stdout)
    if result.returncode:
        print(result.stdout, flush=True)
        raise RuntimeError(f'{label} failed ({result.returncode}); evidence: {out}')
    return result.stdout

for trace in (0, 1):
    for probe in (0, 1):
        name = f'trace{trace}-probe{probe}'
        defines = ['-URISC_PERFORMANCE_TRACE', f'-DRISC_PERFORMANCE_TRACE={trace}', '-URISC_VENDOR_DISPLAY_PROBE']
        if probe:
            defines += ['-DRISC_VENDOR_DISPLAY_PROBE=1']
        if not a.target_only:
            binary = out / ('host-' + name)
            command = [os.environ.get('CXX', 'c++'), '-std=c++17', '-O1', '-g', '-Wall', '-Wextra', '-Werror',
                       '-Wno-misleading-indentation', '-Wno-missing-field-initializers',
                       '-I' + str(ROOT / 'tests/native_display_idf6_shim'), *includes, *defines]
            if a.sanitize:
                command += ['-fsanitize=address,undefined', '-fno-sanitize-recover=all', '-fno-omit-frame-pointer']
            command += [str(ROOT / 'tests/native_display_idf6_test.cpp'), '-o', str(binary)]
            run(command, 'host-compile-' + name, entry['directory'])
            output = run([str(binary)], 'host-run-' + name)
            print(output.strip().splitlines()[-1], flush=True)
            assert (b'RISCRTE_VENDOR_DISPLAY_TIMING_V1' in binary.read_bytes()) == bool(trace)
            if probe:
                for position in (1017, 1018, 1023, 4032, 5036):
                    run([str(binary), str(position)], f'host-probe-timeout-{position}-' + name)
                print('Explicit probe colors, delays and five retained-timeout boundaries: PASS', flush=True)
        if not a.host_only:
            target = out / ('target-' + name + '.o')
            command = list(base)
            command[command.index('-c') + 1] = str(ROOT / 'native/VendorDisplay.cpp')
            command[command.index('-o') + 1] = str(target)
            for option, value in (('-MF', str(target) + '.d'), ('-MT', str(target))):
                if option in command:
                    command[command.index(option) + 1] = value
            command += defines
            run(command, 'target-compile-' + name, entry['directory'])
            assert (b'RISCRTE_VENDOR_DISPLAY_TIMING_V1' in target.read_bytes()) == bool(trace)
            nm = str(Path(base[0]).with_name(Path(base[0]).name.replace('g++', 'nm')))
            symbols = run([nm, '-u', str(target)], 'target-symbols-' + name)
            assert 'spi_device_polling_start' in symbols and 'spi_device_polling_end' in symbols
            assert 'Arduino' not in symbols and 'ESP32QSPI' not in symbols and 'Serial' not in symbols
            print('Actual pinned Xtensa SDK target ' + name + ': PASS', flush=True)

if a.vendor:
    with tempfile.TemporaryDirectory(prefix='co5300-staging-') as directory:
        runtime = Path(directory) / 'runtime'
        command = ['python3', str(ROOT / 'scripts/stage_vendor_display.py'), '--vendor', str(a.vendor),
                   '--idf', str(a.idf), '--runtime', str(runtime)]
        run(command, 'staging-native')
        assert not (runtime / 'lib/WaveshareVendorGfx').exists()
        for name in ('VendorDisplay.cpp', 'VendorDisplayIdf6.inc'):
            assert (runtime / 'src' / name).read_bytes() == (ROOT / 'native' / name).read_bytes()
        proof = json.loads((runtime / 'native-display-idf6-staging.json').read_text())
        assert proof['idf_revision'] == provenance['idf_revision']
        for name, digest in proof['native_sha256'].items():
            assert hashlib.sha256((runtime / 'src' / name).read_bytes()).hexdigest() == digest
        for case in ('wrong-sdk', 'mixed-arduino'):
            bad = Path(directory) / case
            sdk = ROOT if case == 'wrong-sdk' else a.idf
            if case == 'mixed-arduino':
                (bad / 'lib/WaveshareVendorGfx').mkdir(parents=True)
            result = subprocess.run(['python3', str(ROOT / 'scripts/stage_vendor_display.py'), '--vendor', str(a.vendor),
                                     '--idf', str(sdk), '--runtime', str(bad)], text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            (out / ('staging-' + case + '.log')).write_text(result.stdout)
            assert result.returncode != 0 and not (bad / 'src').exists()
        print('Pinned-source staging and wrong-SDK/mixed-library rejection: PASS', flush=True)
print('Native CO5300 contract checks passed. Evidence: ' + str(out), flush=True)
