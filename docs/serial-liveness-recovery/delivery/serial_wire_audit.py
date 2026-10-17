#!/usr/bin/env python3
"""Independent complete wire-trace validator for the pinned .59 host fixture.

The function checks modeled-hardware observations only. It does not execute
firmware, access a device, establish real-time hardware guarantees, or replace
public-asset/source/CI custody checks in the enclosing release auditor.

Interface:
    verify_fixed_sources(product: Path, runtime: Path) -> small source receipt
    validate_serial_wire_log(raw: bytes, case: str, build: str) -> small receipt

No file writes, downloads, subprocess compilation or archive extraction. The
CLI self-test reads twelve existing curated logs and mutates copies in memory.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import zlib

sys.dont_write_bytecode = True
PRODUCT_REVISION = 'd0f95bfcfbef90df58f1bd6e8a3cfe5c495ab8eb'
RUNTIME_REVISION = '48229bd1593a2e24e95bf4537b495ee615990fd3'
MAX_LOG_BYTES = 64 * 1024
MAX_LINE_BYTES = 2048
MAX_RECEIPT_BYTES = 4096
BUILD_MODES = ('normal', 'sanitized')
CADENCES = {'full-progress': 1, 'full-pace8': 8, 'full-pace16': 16,
            'full-pace32': 32, 'full-slow': 50, 'full-stall': 1}
SUCCESS_CASES = frozenset(('full-progress', 'full-pace8', 'full-pace16', 'full-pace32'))
SOURCE_HASHES = {
    'product': {
        'scripts/test_native_serial_liveness.py': '36778c51a01671ee794f1e8062c0c14f81d1acb9da72f0a958bc3c2e5f9814e4',
        'tests/native_serial_liveness/prepare.py': '752383d4e30db18c63af31bde2fb8afa2849acfd043d369b227ed788f120cc49',
        'tests/native_serial_liveness/full_transfer_fixture.inc': '47d573b35bee5769f03f2756afcedf275a6e328a8202618e716c915cf75fc72e',
        'tests/native_serial_liveness/sd_fixture.c': '73d07d77305fc85fe840bdd2f42a4ec128bf797fab5e7d0317232e426dc33006',
    },
    'runtime': {
        'src/runtime/serial/Files.cpp': '97f879319b2436c3975aac521130ee9f8dc37675b9811709b81e93bb8f4457f9',
        'src/runtime/serial/Files.h': '731133e550b5eec4d7a65c88d3e6846c10ebc7438d45683b477ddd5a9ef0bda4',
        'src/bootstrap/Runtime.cpp': '9d1fa51f2c04153767cc2eaaf1a2f90ccb8907d41f2543cf50dacbcd9d42394e',
    },
}
ACTIVE = 'CONFIRM_ACTIVE accepted=0 callback=1 strict=0 discovery_safe=1 continuing=1 session=1 pin=1 retained=0'
SETTLED = 'CONFIRM_SETTLED accepted=1 strict=1 continuing=0 pin=0'
FINAL = 'FINAL ran=1 retained=0 error= lifecycle_retained=0 exit_safe=1 pinned=0 serial_retained=0'
FULL = 'FULL_TRANSFER guarded-replace=1 create=1 readback=1 unrelated-preserved=1'
EXCHANGE = re.compile(
    r'EXCHANGE op=(?P<operation>[^\r\n]+) elapsed_ms=(?P<elapsed>0|[1-9][0-9]*) '
    r'checkpoints=(?P<checkpoints>[1-9][0-9]*) continuing=(?P<continuing>[01]) '
    r'session=(?P<session>0|[1-9][0-9]*) pin=(?P<pin>[01]) pending=(?P<pending>[01]) '
    r'wire=RTEF1 12345678 (?P<sequence>[1-9][0-9]*) (?P<response>[^\r\n]+)')
DISCOVERY_END = re.compile(r'DISCOVERY_END elapsed_ms=(0|[1-9][0-9]*) retained=0 exit=1 pinned=0')


def require(ok, message):
    if not ok:
        raise ValueError(message)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def crc(raw):
    return f'{zlib.crc32(raw) & 0xffffffff:08x}'


def _bounded_receipt(value):
    require(len(json.dumps(value, sort_keys=True).encode()) <= MAX_RECEIPT_BYTES, 'Receipt exceeds 4 KiB')
    return value


def verify_fixed_sources(product, runtime):
    """Read exact Git objects and working files; never fetch or alter sources."""
    for role, root, revision in (('product', Path(product), PRODUCT_REVISION),
                                 ('runtime', Path(runtime), RUNTIME_REVISION)):
        def git(*arguments):
            return subprocess.check_output(['git', '--no-optional-locks', '-C', str(root), *arguments], timeout=60)
        require(git('rev-parse', 'HEAD').decode().strip() == revision, 'Wrong ' + role + ' HEAD')
        require(not git('status', '--porcelain'), 'Dirty ' + role + ' source')
        for name, expected in SOURCE_HASHES[role].items():
            require(sha(git('show', revision + ':' + name)) == expected, 'Pinned Git source differs: ' + name)
            path = root / name
            require(path.is_file() and not path.is_symlink() and sha(path.read_bytes()) == expected,
                    'Working source differs: ' + name)
    return _bounded_receipt({'schema': 1, 'product_revision': PRODUCT_REVISION,
        'runtime_revision': RUNTIME_REVISION, 'source_files': SOURCE_HASHES,
        'hardware_tested': False, 'target_instructions_executed': False})


def expected_exchanges(success):
    """Literal fixture operations with independently derived hex and CRC bytes.

    Entries are (command, complete wire status/body, endpoint pending flag).
    Their position fixes the complete expected monotonically increasing wire
    sequence. No response-prefix or substring-only matches are used.
    """
    old, new, unrelated = b'old', b'new!', b'untouched'
    def path(value):
        return ('PATH 0 ' + value.hex(), '0 PATH ' + str(len(value)), 0)
    prefix = [
        ('HELLO', '0 HELLO 48 511 2', 0),
        ('NS 0', '0 NS 2 1 ' + b'Serial files'.hex(), 0),
        ('NS 1', '0 NS 12 1 ' + b'SD card'.hex(), 0),
        path(b'/old.txt'),
    ]
    if not success:
        return prefix + [('STAT 12', '-4', 0)]
    return prefix + [
        ('STAT 12', '0 STAT 6 3', 0),
        ('GET 12', '0 GET 3', 1),
        ('READ 0', '0 READ 3 ' + old.hex(), 1),
        ('CLOSE', '0 CLOSE ' + crc(old), 0),
        ('PUT 12 replace 4', '0 PUT', 1),
        ('WRITE 0 ' + new.hex(), '0 WRITE 4', 1),
        ('COMMIT ' + crc(new), '0 COMMIT', 0),
        ('GET 12', '0 GET 4', 1),
        ('READ 0', '0 READ 4 ' + new.hex(), 1),
        ('CLOSE', '0 CLOSE ' + crc(new), 0),
        path(b'/new.txt'),
        ('STAT 12', '1 STAT 0 0', 0),
        ('PUT 12 create 4', '0 PUT', 1),
        ('WRITE 0 ' + new.hex(), '0 WRITE 4', 1),
        ('COMMIT ' + crc(new), '0 COMMIT', 0),
        ('GET 12', '0 GET 4', 1),
        ('READ 0', '0 READ 4 ' + new.hex(), 1),
        ('CLOSE', '0 CLOSE ' + crc(new), 0),
        path(b'/unrelated.txt'),
        ('GET 12', '0 GET 9', 1),
        ('READ 0', '0 READ 9 ' + unrelated.hex(), 1),
        ('CLOSE', '0 CLOSE ' + crc(unrelated), 0),
    ]


def validate_serial_wire_log(raw, case, build):
    """Validate one complete archived host log and return at most 4 KiB.

    Caller must independently bind the raw log's hash to its qualification,
    the archive to public release hashes, and source/CI identity. Call
    verify_fixed_sources once before auditing the twelve logs.
    """
    require(type(raw) is bytes and 0 < len(raw) <= MAX_LOG_BYTES, 'Log must be nonempty bytes, at most 64 KiB')
    require(case in CADENCES and build in BUILD_MODES, 'Unknown pinned fixture case/build')
    try:
        text = raw.decode('ascii')
    except UnicodeDecodeError as exc:
        raise ValueError('Wire log is not ASCII') from exc
    require(text.endswith('\n') and '\r' not in text and '\x00' not in text, 'Noncanonical log framing')
    require(all(len(line) <= MAX_LINE_BYTES for line in text.splitlines()), 'Log line exceeds 2 KiB')
    require('runtime error:' not in text and 'ERROR: AddressSanitizer' not in text, 'Sanitizer failure')
    lines = [line for line in text.split('\n') if line]
    success, cadence = case in SUCCESS_CASES, CADENCES[case]
    expected = expected_exchanges(success)
    # One active marker, every exchange, optional full marker, and three ending
    # markers. No omitted, duplicated, reordered or extra diagnostic line passes.
    require(len(lines) == 1 + len(expected) + (1 if success else 0) + 3, 'Incomplete or extra trace lines')
    require(lines[0] == ACTIVE and lines[-3] == SETTLED and lines[-1] == FINAL,
            'Confirmation ordering or final custody differs')
    end = DISCOVERY_END.fullmatch(lines[-2])
    require(end is not None, 'Discovery did not end with released custody')
    total_ms = int(end[1])
    if success:
        require(lines[-4] == FULL, 'Full-transfer summary missing or out of order')
    parsed = []
    for sequence, (command, response, pending) in enumerate(expected, 1):
        row = EXCHANGE.fullmatch(lines[sequence])
        require(row is not None, 'Malformed exchange at sequence ' + str(sequence))
        fields = row.groupdict()
        require(int(fields['sequence']) == sequence and fields['operation'] == command and
                fields['response'] == response, 'Exact command/sequence/wire response differs at ' + str(sequence))
        elapsed, checkpoints = int(fields['elapsed']), int(fields['checkpoints'])
        state = tuple(int(fields[name]) for name in ('continuing', 'session', 'pin', 'pending'))
        if sequence <= 4:
            require(elapsed == 0 and checkpoints == 1 and state == (1, 1, 1, 0),
                    'RAM-only control command delayed or lost active custody')
        elif sequence == 5:
            require(elapsed == (checkpoints - 1) * cadence, 'Measured cadence differs from case')
            if success:
                require(0 < elapsed < 4000 and state == (0, 0, 0, 0), 'Successful STAT custody/deadline differs')
            else:
                require(elapsed == 4000 and state == (1, 0, 1, 0), 'BUSY must end cleanly at modeled deadline')
        else:
            require(elapsed == 0 and checkpoints == 1 and state == (0, 0, 0, pending),
                    'Post-discovery transfer timing/session state differs at ' + str(sequence))
        parsed.append({'elapsed_ms': elapsed, 'checkpoints': checkpoints})
    stat = parsed[4]
    if success:
        require(total_ms == stat['elapsed_ms'], 'Full-transfer total time differs from complete trace')
    else:
        require(stat['elapsed_ms'] < total_ms < 5000, 'BUSY cleanup did not settle within fixture observation bound')
    return _bounded_receipt({'schema': 1, 'case': case, 'build': build,
        'log_bytes': len(raw), 'log_sha256': sha(raw), 'exchange_count': len(expected),
        'exact_wire_sequence_verified': True, 'cadence_ms': cadence,
        'stat': dict(stat, response='success' if success else 'busy'),
        'total_elapsed_ms': total_ms, 'complete_transfer': success,
        'guarded_replacement_verified': success, 'create_verified': success,
        'exact_readback_and_unrelated_preservation_verified': success,
        'busy_no_transfer': not success, 'confirmation_and_final_custody_verified': True,
        'hardware_tested': False, 'target_instructions_executed': False,
        'scope': 'Pinned host fixture with modeled sectors, NVS and scheduling; no physical timing or device acceptance.'})


def self_test(logs, product, runtime):
    source = verify_fixed_sources(product, runtime)
    positives = []
    negatives = {'omitted_exchange': 0, 'wrong_cadence': 0, 'wrong_case_cadence': 0,
                 'altered_wire_response': 0, 'duplicate_exchange': 0}
    def rejected(raw, case, build, control):
        try:
            validate_serial_wire_log(raw, case, build)
        except ValueError:
            negatives[control] += 1
        else:
            raise AssertionError('Accepted negative control: ' + build + '/' + case + '/' + control)
    for build in BUILD_MODES:
        for case in CADENCES:
            path = Path(logs) / (build + '-' + case + '.log')
            require(path.is_file() and not path.is_symlink() and path.stat().st_size <= MAX_LOG_BYTES,
                    'Missing or oversized positive fixture: ' + str(path))
            raw = path.read_bytes()
            receipt = validate_serial_wire_log(raw, case, build)
            positives.append({'case': case, 'build': build, 'sha256': receipt['log_sha256'],
                              'exchanges': receipt['exchange_count']})
            lines = raw.splitlines(keepends=True)
            positions = [i for i, line in enumerate(lines) if line.startswith(b'EXCHANGE ')]
            for position in positions:
                rejected(b''.join(lines[:position] + lines[position+1:]), case, build, 'omitted_exchange')
            position = positions[4]
            changed = list(lines)
            changed[position] = re.sub(rb'elapsed_ms=([0-9]+)',
                lambda match: b'elapsed_ms=' + str(int(match[1]) + 1).encode(), changed[position], count=1)
            rejected(b''.join(changed), case, build, 'wrong_cadence')
            other = {'full-progress': 'full-pace8', 'full-pace8': 'full-pace16',
                     'full-pace16': 'full-pace32', 'full-pace32': 'full-progress',
                     'full-slow': 'full-stall', 'full-stall': 'full-slow'}[case]
            rejected(raw, other, build, 'wrong_case_cadence')
            rejected(raw.replace(b'HELLO 48 511 2', b'HELLO 48 511 9', 1), case, build, 'altered_wire_response')
            rejected(b''.join(lines[:position] + [lines[position]] + lines[position:]), case, build, 'duplicate_exchange')
    require(len(positives) == 12 and negatives == {'omitted_exchange': 228, 'wrong_cadence': 12,
            'wrong_case_cadence': 12, 'altered_wire_response': 12, 'duplicate_exchange': 12},
            'Test matrix differs')
    # This test uses existing curated logs. It does not claim their old metadata
    # is a new native CI run, or replace the final published .59 archive audit.
    return _bounded_receipt({'schema': 1, 'status': 'passed', 'positive_logs': 12,
        'positive_log_inventory_sha256': sha(json.dumps(positives, sort_keys=True).encode()),
        'negative_controls': negatives, 'negative_control_count': sum(negatives.values()),
        'fixed_source_receipt_sha256': sha(json.dumps(source, sort_keys=True).encode()),
        'limits': {'log_bytes': MAX_LOG_BYTES, 'line_bytes': MAX_LINE_BYTES, 'receipt_bytes': MAX_RECEIPT_BYTES},
        'public_release_audited': False, 'hardware_tested': False, 'target_instructions_executed': False})


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--self-test', action='store_true', required=True)
    parser.add_argument('--logs', type=Path, default=Path('/tmp/wave-sd-successor/product/docs/serial-liveness-recovery/native-scheduler'))
    parser.add_argument('--product', type=Path, default=Path('/tmp/wave-sd-successor/product'))
    parser.add_argument('--runtime', type=Path, default=Path('/tmp/runtime-stat-fix-20261017'))
    args = parser.parse_args()
    try:
        print(json.dumps(self_test(args.logs, args.product, args.runtime), sort_keys=True, indent=2))
    except (ValueError, AssertionError, OSError, subprocess.SubprocessError) as exc:
        print('WIRE AUDIT FAILED: ' + str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
