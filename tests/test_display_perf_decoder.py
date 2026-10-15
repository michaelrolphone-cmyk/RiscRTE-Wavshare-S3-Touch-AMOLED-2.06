#!/usr/bin/env python3
"""Strict capture parsing and non-overlapping interpretation of display telemetry."""
from pathlib import Path
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('display_perf', ROOT / 'scripts/decode_display_perf.py')
decoder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(decoder)


def record(sequence, phase, value, timestamp=None, invocation=7):
    return f'RTE_PERF seq={sequence} us={timestamp if timestamp is not None else sequence*1000} interaction=0 invocation={invocation} phase={phase} value={value}'


def batch(start=4, values=None, invocation=7):
    values = values or [64, 640, 20, 80, 1600, 30, 2, 4, 3, 64, 2560, 45, 20, 60, 8]
    return [record(start+i, 8, ((0x40+i) << 24) | value, invocation=invocation) for i, value in enumerate(values)]


def capture(records=None, counters=None, lost=0):
    records = records if records is not None else [record(1, 4, 0), record(2, 5, 0), record(3, 6, 0)] + batch()
    counters = counters or {34: (2, 1004, 80000), 35: (2, 502, 45000), 36: (2, 502, 35000),
                            37: (2, 2, 600), 38: (2, 2, 4000), 39: (1, 1, 700), 26: (32, 32, 36000)}
    lines = [f'RTE_PERF begin schema=1 records={len(records)} lost={lost} overhead_count=20 overhead_min_us=0 overhead_max_us=3 overhead_total_us=22', *records]
    for phase in range(64):
        count, value, duration = counters.get(phase, (0, 0, 0))
        lines.append(f'RTE_PERF counter phase={phase} count={count} value_total={value} duration_us={duration}')
    return '\n'.join(lines + ['RTE_PERF end']) + '\n'


class DecoderTest(unittest.TestCase):
    def test_counts_units_and_no_fps(self):
        summary = decoder.summarize(decoder.parse_capture(capture())[0])
        self.assertFalse(summary['warnings'])
        self.assertEqual(summary['native']['paired_transfer']['mean_duration_us'], 22500)
        self.assertEqual(summary['native']['per_frame_max_transfer']['mean_duration_us'], 300)
        self.assertEqual(summary['application_batches'][0]['stages']['render']['mean_ms'], 10)
        self.assertEqual(summary['application_batches'][0]['stages']['ordered_input_edge_age']['max_ms'], 8)
        self.assertEqual(summary['first_frame_milestones'][0]['first_submit_to_complete_ms'], 1)
        self.assertNotIn('fps', summary)
        self.assertIn('not global maxima', summary['interpretation'])

    def test_multiple_snapshots_and_non_perf_lines(self):
        snapshots = decoder.parse_capture('Boot ok\n' + capture() + 'Other log\n' + capture())
        self.assertEqual(len(snapshots), 2)

    def test_reject_missing_begin_end_record_counter(self):
        good = capture()
        broken = [good.replace('RTE_PERF end\n', ''), good[good.index('\n')+1:],
                  good.replace(record(1, 4, 0)+'\n', ''),
                  good.replace('RTE_PERF counter phase=63 count=0 value_total=0 duration_us=0\n', '')]
        for text in broken:
            with self.subTest(text=text[:50]), self.assertRaises(decoder.CaptureError):
                decoder.parse_capture(text)

    def test_reject_duplicate_overflow_and_nested_snapshot(self):
        good = capture()
        for text in (good.replace('records=18', 'records=18 records=18'),
                     good.replace('schema=1', 'schema=2'),
                     good.replace('seq=1 ', 'seq=4294967296 ', 1),
                     good.replace('us=1000 ', 'us=18446744073709551616 ', 1),
                     good.replace('RTE_PERF end', good.splitlines()[0]),
                     good.replace('counter phase=63', 'counter phase=62'),
                     good.replace('seq=2 ', 'seq=1 ', 1)):
            with self.subTest(text=text[:80]), self.assertRaises(decoder.CaptureError):
                decoder.parse_capture(text)

    def test_partial_application_batch_is_not_mixed_across_invocations(self):
        records = batch()[:6] + batch(start=10, invocation=8)
        summary = decoder.summarize(decoder.parse_capture(capture(records, lost=12))[0])
        self.assertEqual(len(summary['application_batches']), 1)
        self.assertEqual(summary['application_batches'][0]['invocation'], 8)
        self.assertTrue(any('Ignored6' in warning.replace(' ', '') for warning in summary['warnings']))

    def test_suffix_only_batch_is_ignored(self):
        summary = decoder.summarize(decoder.parse_capture(capture(batch()[4:]))[0])
        self.assertFalse(summary['application_batches'])
        self.assertTrue(any('incomplete application' in warning for warning in summary['warnings']))

    def test_saturation_is_lower_bound_without_mean(self):
        values = [0xFFFFFF, 0xFFFFFF, 20] + [0, 0, 0] * 4
        summary = decoder.summarize(decoder.parse_capture(capture(batch(values=values)))[0])
        render = summary['application_batches'][0]['stages']['render']
        self.assertTrue(render['saturated_24bit'])
        self.assertIsNone(render['mean_ms'])

    def test_bad_summary_rejected(self):
        values = [0, 1, 1] + [0, 0, 0] * 4
        with self.assertRaises(decoder.CaptureError):
            decoder.summarize(decoder.parse_capture(capture(batch(values=values)))[0])

    def test_native_inconsistency_reported_without_inventing_metric(self):
        summary = decoder.summarize(decoder.parse_capture(capture(counters={34: (1, 502, 30), 35: (1, 251, 40), 36: (1, 251, 10), 37: (1, 1, 10), 38: (1, 1, 10)}))[0])
        self.assertTrue(any('differs from transfer plus gaps' in warning for warning in summary['warnings']))

    def test_cli_json_and_bad_capture_exit(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'capture.txt'
            path.write_text(capture())
            result = subprocess.run([sys.executable, str(ROOT/'scripts/decode_display_perf.py'), str(path), '--json'], check=True, text=True, capture_output=True)
            self.assertEqual(json.loads(result.stdout)[0]['schema'], 'waveshare.display-perf.v1')
            path.write_text('RTE_PERF end\n')
            result = subprocess.run([sys.executable, str(ROOT/'scripts/decode_display_perf.py'), str(path)], text=True, capture_output=True)
            self.assertEqual(result.returncode, 2)
            self.assertIn('Cannot decode capture', result.stderr)


if __name__ == '__main__':
    unittest.main()
