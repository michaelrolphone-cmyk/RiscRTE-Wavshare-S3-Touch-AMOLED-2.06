#!/usr/bin/env python3
"""Run native raster/contact regressions and host-only profiling from exact source."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import tempfile

from package_native_ui import PINS, ROOT, encoded, git_bytes, require, run, sha, verify_final_pins
from build_native_ui_target import source_snapshot

DIMENSIONS = [(160, 160), (239, 293), (240, 240), (320, 320), (320, 390), (410, 502), (800, 1000)]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('system', 'bridges', 'output', 'target-debug-elf', 'target-objdump'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    require(__debug__, 'Do not run with Python -O')
    verify_final_pins()
    for key in ('system', 'bridges', 'output', 'target_debug_elf', 'target_objdump'):
        setattr(args, key, getattr(args, key).resolve())
    require(not args.output.exists() or not any(args.output.iterdir()), 'Qualification output must be empty')
    for repo, revision in ((args.system, PINS['system_revision']), (args.bridges, PINS['bridge_revision'])):
        require(run('git', '-C', repo, 'rev-parse', 'HEAD').strip() == revision, 'Qualification source HEAD mismatch')
        require(not run('git', '-C', repo, 'diff', 'HEAD', '--name-only').strip(), 'Qualification source is dirty')
    require(not run('git', '-C', args.bridges, 'ls-files', '--others', '--exclude-standard').strip(), 'Unexpected untracked bridge inputs')
    product_revision = run('git', '-C', ROOT, 'rev-parse', 'HEAD').strip()
    require(not run('git', '-C', ROOT, 'diff', 'HEAD', '--name-only').strip(), 'Product provider source is dirty')
    product_inputs = ['drivers/panel_vendor/driver.c', 'tests/provider_log_mock.h']
    product_inputs += sorted(p.relative_to(ROOT).as_posix() for p in (ROOT / 'include').rglob('*') if p.is_file())
    product_hashes = {name: sha((ROOT / name).read_bytes()) for name in product_inputs}
    for name in product_inputs:
        require((ROOT / name).read_bytes() == git_bytes(ROOT, product_revision, name), 'Cadence provider input is not source-owned: ' + name)
    args.output.mkdir(parents=True, exist_ok=True)
    reports = {}
    suites = {}
    with tempfile.TemporaryDirectory(prefix='native-ui-qualification-') as td:
        snapshot = Path(td) / 'system'
        sources = source_snapshot(args.system, PINS['system_revision'], snapshot)
        for name, result_path, count in (
                ('test_watch_native_springboard.py', 'build/watch-native-springboard/results.json', 108),
                ('test_watch_native_springboard_features.py', 'build/watch-native-springboard/feature-results.json', 72),
                ('test_watch_native_fallback.py', 'build/watch-native-fallback/results.json', 24),
                ('test_watch_native_input.py', None, 8)):
            log = run(sys.executable, snapshot / 'scripts' / name)
            (args.output / (name + '.log')).write_text(log)
            if result_path:
                result = json.loads((snapshot / result_path).read_text())
                rows = result['checks'] if isinstance(result, dict) else result
                require(len(rows) == count, 'Incomplete native capability/feature/fallback matrix: ' + name)
                (args.output / (name + '.json')).write_bytes(encoded(result))
                suites[name] = dict(cases=count, report=result, passed=True)
            else:
                require('Native input: 8 native/rotation/sanitizer cases PASS' in log,
                        'Native input/rotation regression did not complete')
                suites[name] = dict(cases=count, passed=True)
        vector_out = args.output / 'native-vectors'
        log = run(sys.executable, snapshot / 'scripts/test_springboard_native_vectors.py',
                  '--output', vector_out, '--target-debug-elf', args.target_debug_elf,
                  '--target-objdump', args.target_objdump)
        (args.output / 'native-vectors.log').write_text(log)
        vector = json.loads((vector_out / 'results.json').read_text())
        require([row['variant'] for row in vector['checks']] == ['normal', 'sanitized']
                and all(row['glyphs'] == 168 and row['draws'] == 12096 and row['winding_cases'] == 2
                        and row['malformed_cases'] == 9 and row['repeat_equal'] and row['negative_clipping_exact']
                        and row['max_edges'] <= row['edge_capacity'] == 512 for row in vector['checks']),
                'Incomplete independent vector qualification')
        require(vector['target_stack']['status'] == 'checked'
                and vector['target_stack']['elf_sha256'] == sha(args.target_debug_elf.read_bytes())
                and vector['max_live_curve_frames'] == 9
                and vector['target_stack']['max_live_curve_frame_bytes'] <= 576,
                'Final target vector recursion proof mismatch')
        suites['test_springboard_native_vectors.py'] = vector
        for label, flags in (('brightness', []), ('brightness-sanitized', ['--sanitize'])):
            out = args.output / label
            log = run(sys.executable, snapshot / 'scripts/test_initial_frame_brightness.py',
                      '--bridges', args.bridges, '--output', out, '--stage-profile', *flags)
            (args.output / (label + '.log')).write_text(log)
            result = json.loads((out / 'results.json').read_text())
            require(len(result) == 32 and all('PASS' in row['result'] for row in result),
                    'Incomplete first-completed-frame brightness matrix')
            require(json.loads((out / 'command.json').read_text()).count('-DPORTABLE_STAGE_PROFILE') == 1,
                    'Brightness fixture lacks final app profiling define')
            reports[label] = result
        require(reports['brightness'] == reports['brightness-sanitized'], 'Sanitized brightness results differ')
        log = run(sys.executable, snapshot / 'scripts/test_watch_async_canvas.py')
        (args.output / 'test_watch_async_canvas.py.log').write_text(log)
        require('real-adapter cases passed in normal/address,undefined modes' in log,
                'Async canvas, elapsed wait or bounded app telemetry regressions failed')
        for case in ('stage-profile-bounded', 'stage-profile-short', 'stage-profile-retained', 'stage-profile-clock-failure',
                     'poll-wait-provider-cost', 'poll-wait-provider-cost-wrap'):
            require(case in log, 'Required diagnostic/wait case did not run: ' + case)
        suites['test_watch_async_canvas.py'] = dict(passed=True, normal_and_sanitized=True)
        for label, flags in (('native-verify', ['--verify']),
                             ('native-verify-sanitized', ['--verify', '--sanitize']),
                             ('host-profile', ['--instrument', '--repeats', '5']),
                             ('host-profile-sanitized', ['--instrument', '--repeats', '5', '--sanitize'])):
            out = args.output / label
            command = [sys.executable, str(snapshot / 'scripts/profile_springboard_full.py'),
                       '--bridges', str(args.bridges), '--output', str(out), '--stage-profile', *flags]
            log = run(*command)
            (args.output / (label + '.log')).write_text(log)
            rows = json.loads((out / 'results.json').read_text())
            if label.startswith('native-verify'):
                require([(row['width'], row['height']) for row in rows] == DIMENSIONS, 'Native geometry coverage differs')
                for row in rows:
                    require(row['result'].startswith('NATIVE_PASS ')
                            and 'physical_contact=exact' in row['result']
                            and 'features=full' in row['result']
                            and 'lifecycle=clean' in row['result'], 'Native raster/contact/lifecycle regression failed')
            else:
                require([(row['width'], row['height']) for row in rows] == [(240, 240), (410, 502)] * 5, 'Host profiling geometry coverage differs')
                for row in rows:
                    require(row['frames'] == 240 and row['render_calls'] == 240, 'Host profile did not render all frames')
                    require(row['instrument_calls'][5] == row['instrument_calls'][6] == 0,
                            'Springboard used the legacy logical-pixel/scaling path')
            reports[label] = rows
            if label.startswith('host-profile'):
                summary = json.loads((out / 'summary.json').read_text())
                require(len(summary) == 2 and all(row['repetitions'] == 5 and row['frames_per_repetition'] == 240 for row in summary), 'Incomplete repeated host profile')
                reports[label + '-summary'] = summary
            require(json.loads((out / 'command.json').read_text()).count('-DPORTABLE_STAGE_PROFILE') == 1, 'Host fixture lacks final app profiling define')
        for label, flags in (('cadence', []), ('cadence-sanitized', ['--sanitize']),
                             ('cadence-old-wait-control', ['--old-wait'])):
            out = args.output / label
            log = run(sys.executable, snapshot / 'scripts/profile_springboard_cadence.py',
                      '--bridges', args.bridges, '--wave', ROOT, '--output', out,
                      '--stage-profile', *flags)
            (args.output / (label + '.log')).write_text(log)
            rows = json.loads((out / 'results.json').read_text())
            require([(r['pair_us'], r['capture_us'], r['raster_checkpoint_us']) for r in rows] ==
                    [(84, 0, 0), (250, 0, 0), (1000, 0, 0), (84, 1, 0), (84, 0, 25), (84, 0, 100)],
                    'Incomplete calibrated cadence scenarios')
            for row in rows:
                require((row['width'], row['height'], row['frames']) == (410, 502, 120)
                        and row['native_contacts'] > 40 and row['catalog_refresh_during_gestures'] == 0,
                        'Cadence physical contact/catalog regression failed')
            require(json.loads((out / 'command.json').read_text()).count('-DPORTABLE_STAGE_PROFILE') == 1,
                    'Cadence fixture lacks final app profiling define')
            reports[label] = rows
        for normal, sanitized in zip(reports['cadence'], reports['cadence-sanitized']):
            stable = lambda row: {k: v for k, v in row.items() if not k.endswith('_host_us_per_frame')}
            require(stable(normal) == stable(sanitized), 'Sanitized calibrated cadence result differs')
        require(reports['native-verify'] == reports['native-verify-sanitized'], 'Sanitized native results differ')
        for normal, sanitized in zip(reports['host-profile'], reports['host-profile-sanitized']):
            for key in ('pixels_hash', 'state_hash', 'instrument_calls'):
                require(normal[key] == sanitized[key], 'Sanitized profile differs: ' + key)
    report = dict(system_revision=PINS['system_revision'], bridge_revision=PINS['bridge_revision'],
                  source_archive_sha256=sources['archive_sha256'], product_revision=product_revision,
                  product_provider_source_sha256=product_hashes, reports=reports, suites=suites,
                  native_frame_and_contact_tests_passed=True, legacy_scaling_path_unused=True,
                  first_completed_frame_brightness_passed=True, target_debug_elf_sha256=sha(args.target_debug_elf.read_bytes()),
                  host_timing_only=True, calibrated_provider_model_only=True, target_instructions_executed=False,
                  hardware_tested=False, device_accessed=False)
    (args.output / 'qualification.json').write_bytes(encoded(report))
    print(json.dumps({key: value for key, value in report.items() if key not in ('reports', 'suites')}, indent=2))


if __name__ == '__main__':
    main()
