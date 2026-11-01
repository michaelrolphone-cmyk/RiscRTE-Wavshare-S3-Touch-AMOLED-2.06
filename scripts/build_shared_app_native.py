#!/usr/bin/env python3
"""Build a source-locked Wave shared-Home candidate; no feed, release or device I/O.

The compiler and all native checks execute in this process. Historical fixed-pin
recipes remain unchanged; only this successor's committed inputs select versions.
"""
import argparse
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys

import native_idf61_build as controlled
import native_idf61_candidate as native
import build_serial_transfer_native as retained
import package_shared_app_native as package
from package_alarm_sleep import make_archive
from package_serial_transfer import require, sha, record, encoded

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / 'docs/shared-app-native'
ROLES = {'product', 'runtime', 'system', 'utilities', 'drivers', 'sdk', 'watch', 'image_helper'}

def pins():
    p = json.loads((DOCS / 'source-pins.json').read_bytes())
    require(p['schema'] == 1 and p['product'] == 'waveshare', 'Unsupported candidate identity')
    require(p['profile'] == 'profiles/serial-transfer-native.cmake', 'Retained transfer profile required')
    return p


def canonical(args, sources, p):
    spec = importlib.util.spec_from_file_location('shared_home_verifier', sources['watch'] / 'scripts/verify_shared_default.py')
    verifier = importlib.util.module_from_spec(spec); spec.loader.exec_module(verifier)
    receipt = verifier.verify(args.first, args.second)
    elf, manifest, first = verifier.check_build(args.first)
    for role in ('system', 'utilities'):
        require(first['verified_dependencies'][role]['commit'] == p[role + '_revision'], 'Home dependency differs: ' + role)
    require(first['compiler_sha256'] == controlled.compiler_family(args.compiler)['s3-gcc']['sha256'], 'Home compiler differs')
    require(record(elf) == p['home']['elf'] and record(manifest) == p['home']['manifest'], 'Home bytes differ')
    require(json.loads(manifest)['version'] == p['home']['version'], 'Home version differs')
    for folder in (args.first, args.second):
        build = json.loads((folder / 'build.json').read_bytes())
        require(build.get('serial_transfer_mode') is True and build.get('automatic_provision') is True, 'Joint Home selection required')
        require(build['artifacts']['default']['defines'].count('-DWATCH_SERIAL_TRANSFER_MODE') == 1, 'Home transfer flag missing or ambiguous')
    return elf, manifest, receipt


def preserved_native_images(baseline, firmware, packed, contract):
    """Keep the released bootloader/NVS prefix; only app/store/bank may change."""
    require(record(baseline) == {k: contract['factory'][k] for k in ('bytes', 'sha256')},
            'Exact released factory required for bootloader preservation')
    require(len(baseline) == 0x1000000, 'Retained factory layout differs')
    size = contract['bootloader']['bytes']
    require(type(size) is int and 0 < size <= 0x8000, 'Invalid released bootloader length')
    released_bootloader = baseline[:size]
    require(record(released_bootloader) == {k: contract['bootloader'][k] for k in ('bytes', 'sha256')},
            'Released bootloader digest differs')
    part_size = contract['partitions']['bytes']
    require(type(part_size) is int and 0 < part_size <= 0x1000, 'Invalid released partition length')
    require(record(baseline[0x8000:0x8000 + part_size]) ==
            {k: contract['partitions'][k] for k in ('bytes', 'sha256')}, 'Released partition digest differs')
    _, transition = native.make_images(baseline, firmware, released_bootloader, packed)
    # make_images' transition is the checked original-bootloader form. Do not
    # return its factory result, which rewrites bootloader padding to 0xff.
    require(len(transition) == len(baseline), 'Factory length changed')
    for start, end in ((0, 0x10000), (0x270000, 0x2f0000),
                       (0x840000, 0xff2000), (0xff3000, 0x1000000)):
        require(transition[start:end] == baseline[start:end], 'Protected released factory range changed')
    return transition, transition, released_bootloader


def qualify(args, sources, proof):
    from read_only_spiffs import read_image
    from prepare_preserving_update import layout, pair
    from current_bootfs import build
    from serial_transfer_qualification import admit_product
    from build_serial_transfer_inputs import runtime_selection
    from serial_transfer_memory import measure, compare
    from qualify_minimal_sd_elfs import qualify as qualify_external
    from qualify_minimal_sd_navigation import qualify as qualify_navigation
    p = pins()
    lock = json.loads(args.lock.read_bytes())
    closure = controlled.validate_build_proof(proof, sources, args.native_build, args.compiler, lock)
    native.verify_sources(lock, sources)
    contract = package.baseline_contract()
    baseline = args.baseline.read_bytes()
    require(record(baseline) == {k: contract['factory'][k] for k in ('bytes', 'sha256')},
            'Exact released 0.1.64 factory required')
    _, _, store = pair(baseline, 0, layout(baseline))
    require(sha(store) == contract['store']['sha256'], 'Exact released store required')
    before = read_image(store, 0x550000)
    package.check_baseline(before, contract)
    # This unchanged verifier checks partitions, Xtensa ELF/BIN correspondence,
    # source markers, actual compiler rows, target bounds and physical hooks.
    native_contract = json.loads(native.CONTRACT.read_bytes())
    blobs, native_proof = native.verify_native(lock, sources, args.native_build, args.compiler, native_contract, baseline)
    serial = retained.package.serial_files_product.check_native(blobs, native_proof, p['product'], sources['runtime'],
        (ROOT / 'profiles/native-idf61.cmake').read_text())
    commands = json.loads((args.native_build / 'compile_commands.json').read_bytes())
    transfer_rows = runtime_selection(commands, sources['runtime'])
    provisioning = retained.qualify_provisioning_native(blobs, native_proof, sources, args.native_build)
    default, manifest, home_proof = canonical(args, sources, p)
    companion = package.companion_files(args.companion, contract)
    expected = {'home': p['home'], 'firmware': {**record(blobs['firmware_bin']),
        'runtime_version': p['runtime_version'], 'runtime_revision': p['runtime_revision']}}
    after, payload, preservation = package.compose(before, companion, default, manifest, blobs['firmware_bin'],
        p['version'], lock['sources']['product']['revision'], expected)
    imports = native.reject_private(after, sources['runtime'])
    packed, packing = build(after, size=0x550000)
    require(build(after, size=0x550000)[0] == packed and read_image(packed, 0x550000) == after,
            'Deterministic store round-trip failed')
    factory, transition, released_bootloader = preserved_native_images(
        baseline, blobs['firmware_bin'], packed, contract)
    require(pair(factory, 0, layout(factory))[1:] == (blobs['firmware_bin'], packed), 'Factory binding differs')
    evidence = args.native_build / 'native-build-evidence'
    admission = admit_product(sources, blobs['firmware_elf'], before, after, native_proof, sanitized=False, receipt_dir=evidence)
    admission_san = admit_product(sources, blobs['firmware_elf'], before, after, native_proof, sanitized=True, receipt_dir=evidence)
    expected_count = sum(name.endswith('.elf') for name in after)
    require(expected_count > 0 and admission['elf_count'] == admission_san['elf_count'] == expected_count,
            'Incomplete product ELF admission')
    baseline_memory = json.loads((retained.package.DOCS / 'baseline-target-memory.json').read_bytes())
    target_memory = compare(measure(blobs['firmware_elf']), baseline_memory['linked'], native_proof['radio_iq'],
                            baseline_memory['iq'], p['target_workspace_bytes'])
    (evidence / 'shared-app-target-memory.json').write_bytes(encoded(target_memory))
    external = qualify_external(sources['runtime'], sources['image_helper'], blobs['firmware_elf'], after, payload,
                                evidence / 'external-apps')
    navigation = qualify_navigation(sources['runtime'], after, payload, evidence / 'navigation')
    from qualify_serial_transfer_runtime import qualify as qualify_transfer, validate as validate_transfer
    transfer = qualify_transfer(sources['runtime'], evidence / 'transfer-mode')
    transfer['compiled_runtime_rows'] = len(transfer_rows)
    validate_transfer(transfer, p['runtime_revision'])
    # Revalidate all immutable sources and native build artifacts after host checks.
    controlled.validate_build_proof(proof, sources, args.native_build, args.compiler, lock)
    native.verify_sources(lock, sources)
    assets = {'factory-candidate-erases-data-0x0.bin': factory, 'firmware.bin': blobs['firmware_bin'],
              'bootloader.bin': released_bootloader, 'partitions.bin': blobs['partitions'], 'store.bin': packed,
              'sd-apps.zip': args.companion.read_bytes(), 'default.elf': default, 'default.json': manifest}
    require(record(assets['sd-apps.zip']) == {k: contract['external_archive'][k] for k in ('bytes', 'sha256')},
            'Companion archive changed during qualification')
    report = dict(schema=1, status='software-qualified-candidate-hardware-pending', product=p['product'], version=p['version'],
        source_revision=lock['sources']['product']['revision'], hardware_tested=False, device_accessed=False,
        published=False, feed_emitted=False, factory_erases_data=True, preserving_update_kit_emitted=False,
        input_lock=lock, controlled_build=closure, native=native_proof, native_rebuilt=True,
        bootloader_preservation={'delivered': record(released_bootloader),
            'rebuilt_evidence_only': record(blobs['bootloader']),
            'released_prefix_bytes': 0x10000, 'released_prefix_sha256': sha(baseline[:0x10000]),
            'factory_prefix_sha256': sha(factory[:0x10000]),
            'partition_table_byte_identical': True},
        default=home_proof, serial_files=serial, provisioning=provisioning, transfer_mode=transfer,
        target_memory=target_memory, baseline_contract=contract, preservation=preservation,
        public_imports=imports, admission=admission, admission_sanitized=admission_san,
        external_apps=external, navigation=navigation, packing=packing,
        artifacts={name: record(raw) for name, raw in assets.items()})
    assets.update({'qualification.json': encoded(report), 'source-lock.json': args.lock.read_bytes(),
                   'source-pins.json': (DOCS / 'source-pins.json').read_bytes()})
    archive = {'qualification.json': assets['qualification.json'], 'canonical-a.json': (args.first / 'build.json').read_bytes(),
               'canonical-b.json': (args.second / 'build.json').read_bytes()}
    for row in lock['native_files'].values():
        archive['build/' + row['path']] = native.safe_path(args.native_build, row['path']).read_bytes()
    for path in evidence.rglob('*'):
        if path.is_file(): archive['build-evidence/' + path.relative_to(evidence).as_posix()] = path.read_bytes()
    assets['candidate-evidence.zip'] = make_archive(archive)
    assets['SHA256SUMS'] = ''.join(sha(raw) + '  ' + name + '\n' for name, raw in sorted(assets.items())).encode()
    args.output.mkdir(parents=True)
    for name, raw in assets.items(): (args.output / name).write_bytes(raw)
    print('Wave shared-Home candidate qualified; physical acceptance not established', flush=True)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', action='append', default=[])
    for name in ('compiler', 'baseline', 'native-build', 'output', 'first', 'second', 'companion'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    require(__debug__, 'Validation cannot be disabled')
    p = pins()
    require(p.get('runtime_revision'), 'Combined Runtime candidate pin is required')
    sources = native.parse_sources(args.source)
    required = ROLES
    require(set(sources) == required, 'Exact source closure required')
    args.native_build, args.output, args.compiler = args.native_build.resolve(), args.output.resolve(), args.compiler.resolve()
    controlled.validate_layout(sources, args.native_build, args.output, ROOT)
    source_pins = {role: native.clean_source(root, native.git(root, 'rev-parse', 'HEAD').decode().strip()) for role, root in sources.items()}
    for role in required - {'product'}:
        require(source_pins[role]['revision'] == p[role + '_revision'], 'Candidate source pin differs: ' + role)
    canonical(args, sources, p)
    require('15.2.0' in controlled.run([args.compiler, '--version']), 'Pinned GCC15 required')
    env = controlled.clean_environment(sources['sdk'], args.compiler)
    cmake = Path(shutil.which('cmake', path=env['PATH'])).resolve()
    if cmake.read_bytes()[:2] == b'#!':
        cmake = (cmake.parent.parent / 'cmake/data/bin/cmake').resolve()
        require(cmake.is_file() and cmake.read_bytes()[:4] == b'\x7fELF', 'Native CMake required')
    env['PATH'] = str(cmake.parent) + ':' + env['PATH']
    tools = controlled.compiler_family(args.compiler)
    selected = [('gcc', str(args.compiler)), ('g++', str(args.compiler.with_name('xtensa-esp-elf-g++'))),
                ('python', sys.executable), ('cmake', str(cmake)), ('ninja', shutil.which('ninja', path=env['PATH']))]
    selected += [(n, str(args.compiler.with_name('xtensa-esp-elf-' + n))) for n in ('as', 'ld', 'ar', 'objcopy', 'objdump', 'readelf', 'nm', 'c++filt')]
    selected += [(n, controlled.compiler_child(args.compiler, n, env)) for n in ('cc1', 'cc1plus', 'collect2')]
    for name, executable in selected:
        require(executable is not None and Path(executable).is_file(), 'Build tool missing: ' + name)
        path = Path(executable).resolve(); tools[name] = {'path': str(path), **controlled.file_row(path)}
    commands = controlled.build_commands(sources, args.native_build, source_pins['runtime']['revision'], cmake)
    commands = [[x.replace('profiles/native-idf61.cmake', 'profiles/serial-transfer-native.cmake') for x in row] for row in commands]
    args.native_build.parent.mkdir(parents=True, exist_ok=True)
    for command in commands: subprocess.run(command, env=env, check=True)
    proof = controlled.collect_build_proof(native, sources, args.native_build, args.compiler, source_pins, commands, env, tools)
    args.lock = args.native_build / 'native-build-evidence/source-lock.json'
    native.freeze(sources, args.native_build, args.compiler, args.lock, p['version'])
    sys.path[:0] = [str(sources['runtime'] / 'scripts'), str(sources['image_helper'] / 'scripts')]
    custody = args.native_build / 'native-build-evidence/locked-native'
    custody.mkdir()
    lock = json.loads(args.lock.read_bytes())
    for row in lock['native_files'].values():
        destination = custody / row['path']; destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(native.safe_path(args.native_build, row['path']), destination)
    qualify(args, sources, proof)


if __name__ == '__main__':
    main()
