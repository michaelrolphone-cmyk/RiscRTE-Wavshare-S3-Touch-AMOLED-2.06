#!/usr/bin/env python3
"""Decode complete RTE_PERF schema1 snapshots; never infer FPS from overlapping spans."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

U32 = (1 << 32) - 1
U64 = (1 << 64) - 1
STAGES = ('render', 'poll', 'catalog_refresh', 'submit_to_observed_complete', 'ordered_input_edge_age')
NATIVE = {
    34: 'frame_first_row_to_last_row',
    35: 'paired_transfer',
    36: 'pre_and_inter_transfer_gaps',
    37: 'per_frame_max_transfer',
    38: 'per_frame_max_gap',
    39: 'aborted_partial_frame',
}


class CaptureError(ValueError):
    pass


def fields(text: str, expected: dict[str, int], line: int) -> dict[str, int]:
    result = {}
    for word in text.split():
        if word.count('=') != 1:
            raise CaptureError(f'line {line}: malformed field {word!r}')
        key, value = word.split('=')
        if key not in expected or key in result or not value.isascii() or not value.isdecimal():
            raise CaptureError(f'line {line}: unknown, duplicate or nonnumeric field {word!r}')
        number = int(value)
        if number > expected[key]:
            raise CaptureError(f'line {line}: {key} is outside its unsigned range')
        result[key] = number
    if result.keys() != expected.keys():
        raise CaptureError(f'line {line}: missing fields {sorted(expected.keys() - result.keys())}')
    return result


def parse_capture(text: str) -> list[dict]:
    """Require begin, declared records, all64 counters, and end for every snapshot."""
    snapshots, current = [], None
    for line_no, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line.startswith('RTE_PERF'):
            continue  # Other ordinary serial diagnostics are not perf records.
        if line.startswith('RTE_PERF begin '):
            if current is not None:
                raise CaptureError(f'line {line_no}: new begin before previous end')
            header = fields(line.removeprefix('RTE_PERF begin '), {
                'schema': U32, 'records': U32, 'lost': U32, 'overhead_count': U32,
                'overhead_min_us': U64, 'overhead_max_us': U64, 'overhead_total_us': U64,
            }, line_no)
            if header['schema'] != 1 or header['records'] > 128:
                raise CaptureError(f'line {line_no}: unsupported schema or ring capacity')
            current = {'header': header, 'records': [], 'counters': {}, 'line': line_no}
        elif line == 'RTE_PERF end':
            if current is None:
                raise CaptureError(f'line {line_no}: end without begin')
            if len(current['records']) != current['header']['records']:
                raise CaptureError(f'line {line_no}: incomplete declared record list')
            if set(current['counters']) != set(range(64)):
                raise CaptureError(f'line {line_no}: incomplete 64-phase counter snapshot')
            snapshots.append(current)
            current = None
        elif line.startswith('RTE_PERF counter '):
            if current is None:
                raise CaptureError(f'line {line_no}: counter outside snapshot')
            counter = fields(line.removeprefix('RTE_PERF counter '), {
                'phase': 63, 'count': U32, 'value_total': U64, 'duration_us': U64,
            }, line_no)
            if len(current['records']) != current['header']['records']:
                raise CaptureError(f'line {line_no}: counters before complete record list')
            if counter['phase'] in current['counters']:
                raise CaptureError(f'line {line_no}: duplicate counter phase')
            current['counters'][counter['phase']] = counter
        elif line.startswith('RTE_PERF seq='):
            if current is None or current['counters']:
                raise CaptureError(f'line {line_no}: record outside record section')
            record = fields(line.removeprefix('RTE_PERF '), {
                'seq': U32, 'us': U64, 'interaction': U32, 'invocation': U32,
                'phase': 63, 'value': U32,
            }, line_no)
            previous = current['records'][-1] if current['records'] else None
            if not record['seq'] or (previous and (record['seq'] <= previous['seq'] or record['us'] < previous['us'])):
                raise CaptureError(f'line {line_no}: nonmonotonic sequence or timestamp')
            current['records'].append(record)
            if len(current['records']) > current['header']['records']:
                raise CaptureError(f'line {line_no}: too many records')
        else:
            raise CaptureError(f'line {line_no}: malformed RTE_PERF line')
    if current is not None:
        raise CaptureError(f'snapshot beginning at line {current["line"]}: missing end')
    if not snapshots:
        raise CaptureError('no complete RTE_PERF snapshot found')
    return snapshots


def application_summaries(records: list[dict]) -> tuple[list[dict], int]:
    """Each flush is15 consecutive tagged counters from the same invocation."""
    batches, pending, discarded = [], [], 0
    for record in records:
        tag = record['value'] >> 24 if record['phase'] == 8 else None
        if pending and (tag != 0x40 + len(pending) or record['invocation'] != pending[0]['invocation']):
            discarded += len(pending)
            pending = []
        if tag == 0x40:
            pending = [record]
        elif pending:
            pending.append(record)
        elif tag is not None and 0x40 < tag <= 0x4E:
            discarded += 1
        if len(pending) == 15:
            batch = {'invocation': pending[0]['invocation'],
                     'first_sequence': pending[0]['seq'], 'last_sequence': pending[-1]['seq'],
                     'timestamp_us': pending[-1]['us'], 'stages': {}}
            values = [r['value'] & 0xFFFFFF for r in pending]
            for index, name in enumerate(STAGES):
                count, total, maximum = values[index * 3:index * 3 + 3]
                saturated = 0xFFFFFF in (count, total, maximum)
                if not saturated and ((count == 0 and (total or maximum)) or maximum > total or (count and total > count * maximum)):
                    raise CaptureError(f'inconsistent stage summary at sequence {pending[index*3]["seq"]}')
                batch['stages'][name] = {
                    'count': count, 'total_ms': total, 'max_ms': maximum,
                    'mean_ms': total / count if count and not saturated else None,
                    'saturated_24bit': saturated,
                }
            batches.append(batch)
            pending = []
    return batches, discarded + len(pending)


def summarize(snapshot: dict) -> dict:
    warnings = []
    if snapshot['header']['lost']:
        warnings.append('Ring records were overwritten; counters remain cumulative, but milestones or application batches may be missing.')
    app, discarded = application_summaries(snapshot['records'])
    if discarded:
        warnings.append(f'Ignored {discarded} tagged records from incomplete application batches.')
    if not app:
        warnings.append('No complete application stage batch: summaries are bounded to once per 2 seconds while work exists, or a final exit flush, and may have been overwritten.')
    native = {}
    for phase, name in NATIVE.items():
        c = snapshot['counters'][phase]
        saturated = c['count'] == U32 or c['value_total'] == U64 or c['duration_us'] == U64
        native[name] = {'phase': phase, 'count': c['count'], 'value_total': c['value_total'],
                        'count_unit': 'aborted_frames' if phase == 39 else 'completed_frames',
                        'value_unit': 'accepted_rows' if phase in (34, 39) else 'paired_windows' if phase in (35, 36) else 'frame_maxima',
                        'duration_us': c['duration_us'],
                        'mean_duration_us': c['duration_us'] / c['count'] if c['count'] and not saturated else None,
                        'saturated': saturated}
        if saturated:
            warnings.append(f'Native phase {phase} contains a saturated counter; totals are lower bounds and its mean is unavailable.')
    frames = snapshot['counters'][34]
    transfer = snapshot['counters'][35]
    gaps = snapshot['counters'][36]
    if frames['count']:
        if any(snapshot['counters'][p]['count'] != frames['count'] for p in range(35, 39)):
            warnings.append('Native completed-frame counts disagree; do not combine these spans.')
        elif frames['duration_us'] != transfer['duration_us'] + gaps['duration_us']:
            warnings.append('Native frame duration differs from transfer plus gaps; counters may be saturated or schema mismatched.')
        if frames['value_total'] != frames['count'] * 502 or transfer['value_total'] != frames['count'] * 251:
            warnings.append('Native row/window counts differ from the expected 410×502 paired-row path.')
    else:
        warnings.append('No completed native display timing frames in this snapshot.')
    first = {}
    for r in snapshot['records']:
        if r['phase'] in (4, 5, 6):
            first.setdefault(r['invocation'], {}).setdefault(r['phase'], r)
    milestones = []
    for invocation, m in first.items():
        entry = {'invocation': invocation}
        for key, start, end in (('first_draw_to_submit_ms', 4, 5), ('first_submit_to_complete_ms', 5, 6)):
            if start in m and end in m and m[end]['us'] >= m[start]['us']:
                entry[key] = (m[end]['us'] - m[start]['us']) / 1000
        if len(entry) > 1:
            milestones.append(entry)
    runtime = {}
    for phase, name in ((26, 'scheduler_wait'), (27, 'provider_poll'), (32, 'provider_native_wait')):
        c = snapshot['counters'][phase]
        runtime[name] = {'count': c['count'], 'value_total': c['value_total'], 'duration_us': c['duration_us']}
    return {'schema': 'waveshare.display-perf.v1',
            'scope': 'Native and Runtime aggregates are cumulative since trace configuration; application batches are reset windows.',
            'native': native, 'runtime': runtime, 'application_batches': app,
            'first_frame_milestones': milestones, 'capture': snapshot['header'], 'warnings': warnings,
            'interpretation': 'Durations overlap. Do not sum inclusive frame/render/poll/transfer spans or derive FPS from them. Native phases37/38 report mean per-frame maxima, not global maxima or percentiles.'}


def render(summary: dict, index: int) -> str:
    lines = [f'Snapshot {index}: {summary["scope"]}']
    for name, metric in summary['native'].items():
        mean = metric['mean_duration_us']
        counts = f'{metric["count"]} {metric["count_unit"]}, {metric["value_total"]} {metric["value_unit"]}'
        lines.append(f'  Native {name}: {counts}, total={metric["duration_us"]} us, mean_per_frame={mean:.3f} us' if mean is not None else f'  Native {name}: {counts}, mean unavailable')
    for name, metric in summary['runtime'].items():
        unit = 'requested_ms' if name != 'provider_poll' else 'poll_scopes'
        lines.append(f'  Runtime {name}: count={metric["count"]}, {unit}={metric["value_total"]}, actual_total={metric["duration_us"]} us')
    for milestone in summary['first_frame_milestones']:
        lines.append('  First frame: ' + ', '.join(f'{k}={v}' for k, v in milestone.items()))
    for batch in summary['application_batches']:
        lines.append(f'  App batch invocation={batch["invocation"]} seq={batch["first_sequence"]}..{batch["last_sequence"]}:')
        for name, metric in batch['stages'].items():
            lines.append(f'    {name}: count={metric["count"]}, total={metric["total_ms"]} ms, max={metric["max_ms"]} ms, mean={metric["mean_ms"]} ms, saturated={metric["saturated_24bit"]}')
    lines += ['  Warning: ' + x for x in summary['warnings']]
    lines.append('  ' + summary['interpretation'])
    return '\n'.join(lines)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('capture', type=Path, help='Plain serial text containing one or more complete perf snapshots')
    parser.add_argument('--json', action='store_true', help='Emit machine-readable summaries with explicit counts and units')
    args = parser.parse_args(argv)
    try:
        summaries = [summarize(s) for s in parse_capture(args.capture.read_text())]
    except (OSError, UnicodeError, CaptureError) as error:
        print(f'Cannot decode capture: {error}', file=sys.stderr)
        return 2
    print(json.dumps(summaries, indent=2) if args.json else '\n\n'.join(render(s, i + 1) for i, s in enumerate(summaries)))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
