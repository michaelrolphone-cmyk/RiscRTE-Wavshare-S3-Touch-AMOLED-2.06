#!/usr/bin/env python3
"""Bound STAT readiness and production Home behavior; native scheduling is separate."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]

def qualify(runtime, watch, system, utilities, sdk, output):
    output.mkdir(parents=True, exist_ok=True)
    fixture = ROOT / 'tests/serial_stat_home'
    sys.path.insert(0, str(watch / 'scripts'))
    from merged_sdk import headers
    receipt = {'schema': 1, 'hardware_tested': False, 'leak_sanitizer': False,
        'scope': 'Exact product SD driver and FatFs, actual RuntimeFiles adapter, production Home controllers. Modeled card, worker, guard and peripheral services. Checkpoint return values are injected. No native scheduler or target instruction execution claim.',
        'cases': [], 'compilations': [], 'inputs_sha256': {}}
    dependencies = set()
    def record(path):
        dependencies.add(Path(path).resolve())
    with tempfile.TemporaryDirectory(prefix='wave-stat-home-') as temp:
        work = Path(temp)
        home_sdk = headers(work, system, utilities, watch)
        original = watch / 'tests/fast_wake_clock_test.c'
        text = original.read_text()
        for before, after in [('static const risc_runtime_api_v1 fast_runtime=',
                              'static risc_runtime_api_v1 fast_runtime='),
                             ('int main(void){', 'int inherited_fast_main(void){')]:
            assert text.count(before) == 1, 'Pinned fixture anchor changed'
            text = text.replace(before, after)
        text += (fixture / 'home_sequence.inc').read_text()
        generated = output / 'home_sequence.c'
        generated.write_text(text)
        record(original); record(fixture / 'home_sequence.inc'); record(__file__)
        for mode in ('normal', 'sanitized'):
            sanitizer = [] if mode == 'normal' else ['-fsanitize=address,undefined',
                '-fno-sanitize-recover=all', '-fno-omit-frame-pointer', '-no-pie']
            common = ['-O1', '-g', '-Wall', '-Wextra', '-Werror', '-Wno-unused-function',
                '-Wno-misleading-indentation', '-Wno-overflow', *sanitizer]
            commands = []
            def run(command):
                command = list(map(str, command)); commands.append(command)
                subprocess.run(command, check=True)
            def compile_one(language, source, flags, name):
                obj = work / (name + '.o'); dep = work / (name + '.d')
                run([language, '-std=c11' if language == 'cc' else '-std=c++17',
                     *flags, '-MMD', '-MF', dep, '-c', source, '-o', obj])
                for token in dep.read_text().replace('\\\n', ' ').split(':', 1)[1].split():
                    record(token)
                return obj
            def test(binary, case, group):
                result = subprocess.run([str(binary), case], capture_output=True, text=True,
                    timeout=120, env={**os.environ, 'ASAN_OPTIONS': 'detect_leaks=0',
                                      'UBSAN_OPTIONS': 'halt_on_error=1'})
                (output / f'{mode}-{group}-{case}.log').write_text(result.stdout + result.stderr)
                print(result.stdout, end='', flush=True)
                if result.returncode: print(result.stderr, flush=True)
                result.check_returncode()
                receipt['cases'].append({'build': mode, 'group': group, 'case': case,
                                         'stdout': result.stdout, 'stderr': result.stderr})
            provider_flags = [*common, '-I'+str(sdk), '-I'+str(ROOT/'include')]
            provider = [compile_one('cc', source, provider_flags, 'provider-'+str(i))
                for i, source in enumerate([fixture/'provider.c',
                    ROOT/'lib/storage_fatfs/fatfs/ff.c', ROOT/'lib/storage_fatfs/fatfs/ffunicode.c'])]
            client_flags = [*provider_flags, '-I'+str(runtime/'src')]
            client = compile_one('c++', fixture/'readiness.cpp', client_flags, 'readiness')
            binary = work/'readiness'
            run(['c++', *common, client, *provider, '-o', binary])
            for case in ('active-session', 'sleep-prepared', 'owner-refused', 'io-unavailable'):
                test(binary, case, 'readiness')
            defines = ['WATCH_COMPACT_NOVA_ASSETS', 'WATCH_SHARED_PREFERENCE_HEADERS',
                'PORTABLE_LOW_BATTERY', 'WATCH_COMPRESSED_CALENDAR_ALPHA',
                'WATCH_COMPRESSED_FACE_ALPHA', 'WATCH_FAST_WAKE', 'WATCH_COLD_BOOT_ANIMATION',
                'PORTABLE_WATCH_NATIVE_HEIGHT', 'PORTABLE_RTC_UTC8_DENVER',
                'PORTABLE_PREFERENCE_STORE', 'WATCH_ATOMIC_PREFERENCES',
                'PORTABLE_QUICK_ATOMIC_PREFERENCES', 'PORTABLE_QUICK_RADIOS',
                'WATCH_AUTOMATIC_PROVISION', 'WATCH_CRASH_REPORT',
                'CRASH_REPORT_SESSION_FILES=1', 'WATCH_CRASH_REPORT_NAMESPACE=61',
                'TEST_WIDTH=410u', 'TEST_HEIGHT=502u']
            flags = [*common, *['-D'+d for d in defines], *['-I'+str(p) for p in
                (home_sdk, watch/'include', watch, watch/'tests', system/'lib/PortableApps/src')]]
            sources = [generated, *[watch/'apps/clock'/n for n in
                ('nova/nova.c', 'points_projection.c', 'viewport.c', 'capability_clients.c', 'quick_radios.c')],
                *[system/'lib/PortableApps/src'/n for n in ('quick_actions.c', 'quick_render.c',
                    'quick_session.c', 'PortableAutomaticProvision.c', 'PortableNetworkSession.c')]]
            objects = [compile_one('cc', source, [*flags, *(['-DWATCH_CONTEXTS_CLIENT'] if i else [])],
                                  'home-'+str(i)) for i, source in enumerate(sources)]
            bridge = compile_one('c++', fixture/'home_bridge.cpp', client_flags, 'bridge')
            effect = compile_one('c++', watch/'apps/clock/effects/boot.cpp', flags, 'effect')
            binary = work/'home'
            run(['c++', *common, effect, bridge, *objects, *provider, '-o', binary])
            for case in ('unavailable', 'busy', 'late-retained'):
                test(binary, case, 'home')
            receipt['compilations'].append({'build': mode, 'commands': commands,
                'home_binary_sha256': hashlib.sha256(binary.read_bytes()).hexdigest()})
        for path in sorted(dependencies):
            receipt['inputs_sha256'][str(path)] = hashlib.sha256(path.read_bytes()).hexdigest()
    assert len(receipt['cases']) == 14
    (output/'qualification.json').write_text(json.dumps(receipt, indent=2)+'\n')
    return receipt

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('runtime', 'watch', 'system', 'utilities', 'sdk', 'output'):
        parser.add_argument('--'+name, type=Path, required=True)
    args = parser.parse_args()
    qualify(**{name: path.resolve() for name, path in vars(args).items()})

if __name__ == '__main__': main()
