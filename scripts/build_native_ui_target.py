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
import struct
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


def native_vector_proof(debug_elf, compact_elf, vector_source, disassembly):
    """Bind live presenter callbacks, vector calls and exact outlines to shipped bytes."""
    from elftools.elf.elffile import ELFFile
    debug, compact = (ELFFile(io.BytesIO(data)) for data in (debug_elf, compact_elf))
    for elf in (debug, compact):
        require(elf.elfclass == 32 and elf.little_endian and elf['e_machine'] == 'EM_XTENSA',
                'Native vector proof requires the Xtensa ELF32 target')
    sections = []
    allocated = lambda elf: {s.name: s for s in elf.iter_sections() if s['sh_flags'] & 2}
    ds, cs = allocated(debug), allocated(compact)
    require(ds.keys() == cs.keys(), 'Debug/compact allocated section sets differ')
    for name, section in ds.items():
        other = cs[name]
        for key in ('sh_addr', 'sh_size', 'sh_type', 'sh_flags'):
            require(section[key] == other[key], 'Debug/compact section layout differs: ' + name)
        if section['sh_type'] != 'SHT_NOBITS':
            require(section.data() == other.data(), 'Debug/compact allocated bytes differ: ' + name)
        sections.append(dict(name=name, address=section['sh_addr'], bytes=section['sh_size']))
    table = debug.get_section_by_name('.symtab')
    require(table is not None, 'Native vector debug symbol table absent')
    symbols = list(table.iter_symbols())
    def symbol(name, kind):
        rows = [s for s in symbols if s.name.split('$')[0] == name and s['st_info']['type'] == kind]
        require(len(rows) == 1 and isinstance(rows[0]['st_shndx'], int), 'Live native symbol missing or ambiguous: ' + name)
        row = rows[0]; section = debug.get_section(row['st_shndx'])
        offset = row['st_value'] - section['sh_addr']
        require(section['sh_flags'] & 2 and row['st_size'] > 0 and offset >= 0 and
                offset + row['st_size'] <= section['sh_size'], 'Native symbol outside allocated image: ' + name)
        if kind == 'STT_FUNC':
            require(section['sh_flags'] & 4, 'Native function is not executable: ' + name)
        return row, section, offset
    callbacks = ('np_begin', 'np_circle', 'np_icon', 'np_caption', 'np_contact', 'np_clock')
    function_names = callbacks + ('np_icon_color', 'np_vector_draw', 'np_vector_quad',
        'np_vector_cubic', 'np_vector_line', 'np_vector_read', 'np_native_extent',
        'np_native_measure', 'np_native_text_glyph')
    functions = {name: symbol(name, 'STT_FUNC')[0] for name in function_names}
    objects = {}
    for name, size in dict(np_vector_glyphs=168*18, np_vector_icons=30*8, np_vector_text=190,
            np_view=28, np_vector_data=19741, np_vector_edges=512*16,
            np_vector_hits=512*4, np_vector_winding=512, np_vector_coverage=128*2).items():
        row, section, offset = symbol(name, 'STT_OBJECT')
        require(row['st_size'] == size, 'Native vector object size changed: ' + name)
        objects[name] = dict(address=row['st_value'], bytes=size)
    match = re.search(r'np_vector_packed\[\]\s*=\s*\{([^}]+)\}', vector_source)
    require(match is not None, 'Committed vector outline payload absent')
    expected = bytes(int(value) for value in match.group(1).split(',') if value.strip())
    row, section, offset = symbol('np_vector_packed', 'STT_OBJECT')
    require(row['st_size'] == len(expected) and section.data()[offset:offset+len(expected)] == expected,
            'Shipped native outlines differ from committed vector source')
    objects['np_vector_packed'] = dict(address=row['st_value'], bytes=len(expected), sha256=sha(expected))
    row, section, offset = symbol('np_view', 'STT_OBJECT')
    pointers = struct.unpack('<7I', section.data()[offset:offset+28])
    require(pointers == (28, *(functions[name]['st_value'] for name in callbacks)),
            'Native presenter callback table does not bind the live native functions')
    def read_address(address):
        for section in cs.values():
            offset = address - section['sh_addr']
            if section['sh_type'] != 'SHT_NOBITS' and 0 <= offset <= section['sh_size'] - 4:
                return struct.unpack('<I', section.data()[offset:offset+4])[0]
        raise ValueError('Native call literal outside the compact image')
    calls = []
    for caller, callee in (('np_icon', 'np_icon_color'), ('np_icon_color', 'np_vector_draw'),
                            ('np_caption', 'np_vector_draw')):
        row = functions[caller]
        instructions = []
        for line in disassembly.splitlines():
            match = re.match(r'\s*([0-9a-f]+):\s+[0-9a-f]+\s+(\S+)\s*(.*)', line)
            if match and row['st_value'] <= int(match[1], 16) < row['st_value'] + row['st_size']:
                instructions.append((int(match[1], 16), match[2], match[3]))
        found = []
        for index, (address, opcode, operands) in enumerate(instructions):
            load = re.match(r'(a\d+),\s*([0-9a-f]+)', operands) if opcode == 'l32r' else None
            if not load or read_address(int(load[2], 16)) != functions[callee]['st_value']:
                continue
            register = load[1]
            for call_address, op, args in instructions[index+1:]:
                if op == 'callx8' and args.strip() == register:
                    found.append(dict(load_address=address, literal_address=int(load[2], 16), call_address=call_address)); break
                if op.startswith('call') or (args.split(',')[0].strip() == register and
                        not op.startswith(('s8i', 's16i', 's32i', 'b'))):
                    break
        require(found, 'Live native vector call binding absent: ' + caller + ' -> ' + callee)
        calls.append(dict(caller=caller, callee=callee, bindings=found))
    return dict(debug_elf_sha256=sha(debug_elf), compact_elf_sha256=sha(compact_elf),
                allocated_sections_identical=sections, presenter_callbacks=list(callbacks),
                live_functions={name: dict(address=row['st_value'], bytes=row['st_size'])
                                for name, row in functions.items()}, vector_objects=objects,
                live_vector_calls=calls, diagnostic_string_required=False)


def test_native_vector_gate(debug_elf, compact_elf, vector_source, disassembly, baseline_debug, baseline):
    """Exercise the real linked target, including marker-only and byte-tamper impostors."""
    from elftools.elf.elffile import ELFFile
    rejected = []
    def reject(name, debug, compact, source=vector_source, assembly=disassembly):
        try:
            native_vector_proof(debug, compact, source, assembly)
        except ValueError:
            rejected.append(name)
        else:
            raise ValueError('Invalid native vector fixture accepted: ' + name)
    reject('exact-.43-baseline', baseline_debug, baseline)
    marker = b'native-springboard-vector-v1\0'
    reject('marker-only-impostor', baseline_debug + marker, baseline + marker)
    reject('missing-native-call', debug_elf, compact_elf, assembly=disassembly.replace('callx8', 'retw.n'))
    elf = ELFFile(io.BytesIO(debug_elf)); rows = list(elf.get_section_by_name('.symtab').iter_symbols())
    for name in ('np_vector_packed', 'np_view', 'np_vector_draw'):
        row = next(s for s in rows if s.name.split('$')[0] == name)
        section = elf.get_section(row['st_shndx']); relative = row['st_value'] - section['sh_addr']
        other = ELFFile(io.BytesIO(compact_elf)).get_section_by_name(section.name)
        at = other['sh_offset'] + relative
        changed = bytearray(compact_elf); changed[at] ^= 1
        reject('compact-byte-tamper-' + name, debug_elf, bytes(changed))
        if name != 'np_vector_draw':
            changed_debug = bytearray(debug_elf); changed_debug[section['sh_offset'] + relative] ^= 1
            reject('matching-debug-and-compact-tamper-' + name, bytes(changed_debug), bytes(changed))
    return dict(passed=True, negative_cases=rejected, real_target_positive=True)


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
            native_vector = None
            native_vector_tests = None
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
                debug_data = (out / 'springboard.debug.elf').read_bytes()
                vector_source = (system / 'lib/PortableApps/fonts/native_vectors.inc').read_text()
                assembly = run(str(args.compiler).removesuffix('gcc') + 'objdump', '-d', out / 'springboard.debug.elf')
                native_vector = native_vector_proof(debug_data, data, vector_source, assembly)
                native_vector_tests = test_native_vector_gate(debug_data, data, vector_source, assembly,
                    (args.output / 'baseline/springboard.debug.elf').read_bytes(),
                    (args.output / 'baseline/springboard.elf').read_bytes())
                require(command.count('-DPORTABLE_STAGE_PROFILE') == 1, 'Bounded app profiling define missing or repeated')
                app_profile = app_profile_proof((out / 'springboard.debug.elf').read_bytes())
                vector_stack = vector_stack_proof(system, args.compiler, out / 'springboard.debug.elf')
                require(json.loads((system / 'Apps/springboard.json').read_text())['version'] == PINS['springboard_manifest_version'], 'Source Springboard manifest version mismatch')
                require(len(data) <= PINS['springboard_max_bytes'], 'Springboard exceeds measured .43-preserving store budget')
            normalized = [x.replace(str(system), '{system}').replace(str(bridges), '{bridges}').replace(str(out), '{output}').replace(str(args.compiler), '{compiler}') for x in command]
            results.append(dict(profile=label, sha256=sha(data), bytes=len(data), imports=imports,
                                exports=exports, command=normalized, source=source_proof,
                                compaction=compaction, elf_validator_passed=True,
                                font_regeneration=font_regeneration, app_profile=app_profile, vector_stack=vector_stack,
                                native_vector=native_vector, native_vector_gate_tests=native_vector_tests))
        report = dict(results=results, bridge=bridge_proof, compiler=version,
                      compiler_binary_sha256=sha(args.compiler.read_bytes()),
                      baseline_reproduced=True, device_accessed=False, hardware_tested=False)
        (args.output / 'target-proof.json').write_text(json.dumps(report, indent=2, sort_keys=True) + '\n')
        print(json.dumps(dict(output=str(args.output), baseline_reproduced=True,
                             results=[{k: row[k] for k in ('profile', 'sha256', 'bytes')} for row in results]), indent=2))


if __name__ == '__main__':
    main()
