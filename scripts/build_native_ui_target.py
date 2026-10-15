#!/usr/bin/env python3
"""Reproduce the shipped .43 Springboard, then build the finalized native UI.

Compile only isolated git archives, preserving all existing deployment features.
Neither this builder nor the packager accesses hardware or publishes assets.
"""
import argparse
import hashlib
import io
import json
import os
import re
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile

from package_native_ui import PINS, ROOT, require, run, sha, verify_final_pins


def source_snapshot(repo, revision, output):
    require(run('git', '-C', repo, 'rev-parse', revision).strip() == revision,
            'Exact source revision unavailable: ' + revision)
    data = subprocess.check_output(['git', '-C', str(repo), 'archive', revision])
    output.mkdir(parents=True)
    with tarfile.open(fileobj=io.BytesIO(data)) as source:
        source.extractall(output, filter='data')
    hashes = {p.relative_to(output).as_posix(): sha(p.read_bytes())
              for p in sorted(output.rglob('*')) if p.is_file()}
    return {'revision': revision, 'archive_sha256': sha(data), 'files': hashes}


def deployment_command(system, bridges, compiler, output, candidate):
    original = json.loads((ROOT / 'docs/catalog-display-custody/target-command.json').read_text())
    old_system = next(x[:-len('/Apps/springboard.c')] for x in original if x.endswith('/Apps/springboard.c'))
    old_bridges = next(x[:-len('/apps/clock/portable_navigation.c')] for x in original if x.endswith('/apps/clock/portable_navigation.c'))
    command = [x.replace(old_system, str(system)).replace(old_bridges, str(bridges)) for x in original]
    command[0] = str(compiler)
    command[command.index('-o') + 1] = str(output / 'springboard.elf')
    mapping = output / 'exports.map'
    mapping.write_text('{global: app_main; app_module_init; app_module_fini;local:*;};\n')
    command = ['-Wl,--version-script=' + str(mapping) if x.startswith('-Wl,--version-script=') else x for x in command]
    if candidate:
        remove, add = PINS['remove_springboard_flags'], PINS['add_springboard_flags']
        require(len(remove) == len(set(remove)) and len(add) == len(set(add)), 'Duplicate deployment flag')
        require(all(x.startswith('-DPORTABLE_') or x.startswith('-DWATCH_') for x in remove + add), 'Only explicit deployment defines can change')
        require(all(command.count(x) == 1 for x in remove), 'Removed flag absent or duplicated')
        command = [x for x in command if x not in remove]
        require(not set(add) & set(command), 'Added flag already present')
        command.extend(add)
    return command


def regenerate_fonts(system, bridges, python):
    prefix = 'lib/PortableApps/fonts/'
    names = [prefix + name for name in ('native_vectors.inc', 'native_vectors_sources.json')]
    before = {name: (system / name).read_bytes() for name in names}
    for name in ('Orbitron-500.ttf', 'Rajdhani-600.ttf'):
        require((system / prefix / 'native_sources' / name).read_bytes() ==
                (bridges / 'apps/clock/nova/fonts' / name).read_bytes(),
                'Committed text font differs from pinned original: ' + name)
    run(python, system / 'scripts/generate_springboard_native_vectors.py')
    after = {name: (system / name).read_bytes() for name in names}
    require(after[names[0]] == before[names[0]],
            'Native vector regeneration differs from exact committed output')
    original, regenerated = (json.loads(value[names[1]]) for value in (before, after))
    for metadata in (original, regenerated):
        generator = metadata['generator']
        require(generator['fonttools'] == '4.61.1' and generator['python'] == '3.12.14',
                'Unpinned vector generator versions')
        require(generator['brotli']['version'] == '1.1.0' and
                generator['brotli']['implementation'] in ('libbrotlidec', 'python-brotli'),
                'Unpinned vector decoder version')
    # The pinned C and Python Brotli implementations must yield identical vectors.
    # Keep their actual implementation names in evidence rather than inventing one.
    def comparable(metadata):
        value = json.loads(json.dumps(metadata))
        value['generator']['brotli'].pop('implementation')
        return value
    require(comparable(original) == comparable(regenerated),
            'Regenerated vector provenance differs from committed inputs/output')
    for name, data in before.items():
        (system / name).write_bytes(data)
    return dict(source_sha256={name: sha(data) for name, data in before.items()},
                committed_generator=original['generator'],
                regeneration_generator=regenerated['generator'], byte_exact_vectors=True)


def app_profile_proof(debug_elf):
    from elftools.elf.elffile import ELFFile
    image = ELFFile(io.BytesIO(debug_elf))
    symbols = list(image.get_section_by_name('.symtab').iter_symbols())
    state = [row for row in symbols if row.name.startswith('stage_profile$')
             and row['st_info']['type'] == 'STT_OBJECT']
    require(len(state) == 1 and state[0]['st_size'] == 80,
            'App stage aggregate state is not the qualified bounded 80-byte layout')
    functions = {}
    for name in ('stage_profile_trace', 'stage_profile_flush', 'stage_profile_counter'):
        rows = [row for row in symbols if row.name.split('$')[0] == name
                and row['st_info']['type'] == 'STT_FUNC' and row['st_shndx'] != 'SHN_UNDEF']
        require(len(rows) == 1 and rows[0]['st_size'] > 0, 'Live app trace function missing: ' + name)
        functions[rows[0].name] = rows[0]['st_size']
    return dict(debug_elf_sha256=sha(debug_elf), state_bytes=80, live_functions=functions,
                phase=8, tags=list(range(0x40, 0x4f)), first_frame_milestones=[4, 5, 6],
                compile_define='-DPORTABLE_STAGE_PROFILE')


def vector_stack_proof(system, compiler, debug_path):
    text = run(str(compiler).removesuffix('gcc') + 'objdump', '-d', debug_path)
    frames = {}
    for name in ('np_vector_quad', 'np_vector_cubic', 'np_vector_line', 'np_vector_draw'):
        found = re.findall(r'<(' + name + r'(?:\$[^>]*)?)>:\n\s*[0-9a-f]+:\s*[0-9a-f]+\s+entry\s+a1,\s*(\d+)', text)
        require(len(found) == 1, 'Ambiguous or missing linked vector function prologue: ' + name)
        frames[found[0][0]] = int(found[0][1])
    source = (system / 'lib/PortableApps/src/nova_vector.inc').read_text()
    require(source.count('if(depth>=8 ||') == 2, 'Reviewed vector recursion bound changed')
    curve_frames = [value for key, value in frames.items() if key.split('$')[0] in ('np_vector_quad', 'np_vector_cubic')]
    require(max(curve_frames) <= 64, 'Linked vector recursive stack frame exceeds reviewed target bound')
    return dict(linked_lto_frame_bytes=frames, maximum_recursive_curve_frames=9,
                maximum_recursive_curve_bytes=9 * max(curve_frames),
                total_task_stack_high_water_measured=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('system', 'bridges', 'compiler', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--baseline-only', action='store_true', help='Reproduce .43 without selecting any pending candidate inputs')
    parser.add_argument('--font-python', default=sys.executable, help='Python with the pinned fontTools/Brotli vector generator')
    args = parser.parse_args()
    require(__debug__, 'Do not run with Python -O')
    if not args.baseline_only:
        verify_final_pins()
    for key, value in vars(args).items():
        if isinstance(value, Path):
            setattr(args, key, value.resolve())
    require(not args.output.exists() or not any(args.output.iterdir()), 'Output must be empty')
    version = run(args.compiler, '--version').splitlines()[0]
    require(version == PINS['compiler_version'], 'Unpinned Xtensa compiler version')
    if not args.baseline_only:
        for repo, revision in ((args.system, PINS['system_revision']), (args.bridges, PINS['bridge_revision'])):
            require(run('git', '-C', repo, 'rev-parse', 'HEAD').strip() == revision, 'Build repository HEAD mismatch')
            require(not run('git', '-C', repo, 'diff', 'HEAD', '--name-only').strip(), 'Tracked build sources are dirty')
    args.output.mkdir(parents=True, exist_ok=True)
    results = []
    with tempfile.TemporaryDirectory(prefix='native-ui-source-') as td:
        sources = Path(td)
        bridges = sources / 'bridges'
        bridge_proof = source_snapshot(args.bridges, PINS['bridge_revision'], bridges)
        sys.path.insert(0, str(bridges / 'scripts'))
        from compact_current_elf import compact
        from normalize_xtensa_relocations import normalize
        variants = [('baseline', PINS['baseline_system'])]
        if not args.baseline_only:
            variants.append(('candidate', PINS['system_revision']))
        for label, revision in variants:
            system = sources / label
            source_proof = source_snapshot(args.system, revision, system)
            font_regeneration = regenerate_fonts(system, bridges, args.font_python) if label == 'candidate' else None
            app_profile = None
            vector_stack = None
            out = args.output / label
            out.mkdir()
            command = deployment_command(system, bridges, args.compiler, out, label == 'candidate')
            run(*command)
            normalize(out / 'springboard.elf')
            compaction = compact(out / 'springboard.elf', str(args.compiler), debug_path=out / 'springboard.debug.elf')
            validator = out / 'validate-elf'
            run(os.environ.get('CC', 'cc'), '-std=c11', '-Wall', '-Wextra', '-Werror',
                '-I' + str(system / 'test/native_apps/stubs'), '-I' + str(system / 'lib/elf_loader/include'),
                system / 'lib/elf_loader/src/esp_elf_validate.c', system / 'test/native_apps/validate_test.c',
                '-o', validator)
            run(validator, out / 'springboard.elf')
            data = (out / 'springboard.elf').read_bytes()
            symbols = run(str(args.compiler).removesuffix('gcc') + 'nm', '-D', out / 'springboard.elf')
            imports = sorted({line.split()[-1] for line in symbols.splitlines() if ' U ' in ' ' + line})
            exports = sorted({line.split()[-1] for line in symbols.splitlines() if len(line.split()) >= 3 and line.split()[-2] in ('T', 'D', 'B', 'R')})
            if label == 'baseline':
                require(sha(data) == PINS['baseline_springboard_sha256'], 'Shipped .43 Springboard did not reproduce exactly')
            else:
                require(set(imports) <= set(results[0]['imports']), 'New Springboard Runtime imports require separate review')
                require(exports == results[0]['exports'], 'Springboard exports changed')
                require(sha(data) != PINS['baseline_springboard_sha256'], 'Candidate Springboard unchanged')
                require(b'native-springboard-vector-v1\0' in data, 'Native vector presenter marker absent')
                require(command.count('-DPORTABLE_STAGE_PROFILE') == 1, 'Bounded app profiling define missing or repeated')
                app_profile = app_profile_proof((out / 'springboard.debug.elf').read_bytes())
                vector_stack = vector_stack_proof(system, args.compiler, out / 'springboard.debug.elf')
                require(json.loads((system / 'Apps/springboard.json').read_text())['version'] == PINS['springboard_manifest_version'], 'Source Springboard manifest version mismatch')
                require(len(data) <= PINS['springboard_max_bytes'], 'Springboard exceeds measured .43-preserving store budget')
            normalized = [x.replace(str(system), '{system}').replace(str(bridges), '{bridges}').replace(str(out), '{output}').replace(str(args.compiler), '{compiler}') for x in command]
            results.append(dict(profile=label, sha256=sha(data), bytes=len(data), imports=imports,
                                exports=exports, command=normalized, source=source_proof,
                                compaction=compaction, elf_validator_passed=True,
                                font_regeneration=font_regeneration, app_profile=app_profile, vector_stack=vector_stack))
        report = dict(results=results, bridge=bridge_proof, compiler=version,
                      compiler_binary_sha256=sha(args.compiler.read_bytes()),
                      baseline_reproduced=True, device_accessed=False, hardware_tested=False)
        (args.output / 'target-proof.json').write_text(json.dumps(report, indent=2, sort_keys=True) + '\n')
        print(json.dumps(dict(output=str(args.output), baseline_reproduced=True,
                             results=[{k: row[k] for k in ('profile', 'sha256', 'bytes')} for row in results]), indent=2))


if __name__ == '__main__':
    main()
