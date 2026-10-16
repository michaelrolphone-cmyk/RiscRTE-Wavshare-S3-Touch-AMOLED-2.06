#!/usr/bin/env python3
"""Exact authority, preservation, idempotence and rejection checks; no devices."""
import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from home_retained_wake_policy import CAPABILITY, GRANT, REQUIREMENT, provision


class HomeWakePolicyTest(unittest.TestCase):
    def setUp(self):
        self.manifest = {"type": "application", "id": "twatch-clock",
                         "version": "0.15.4", "file_name": "default.elf",
                         "entry": "app_main", "requires": [
                             {"capability": "runtime.realtime-control", "api": 1}],
                         "optional": [{"capability": "board.battery", "api": 1}]}
        self.policy = {"manifest": "default.json", "grants": [
            {"capability": "runtime.realtime-control", "api": 1, "instance_id": 0}]}

    def test_exact_addition_and_no_input_mutation(self):
        before = copy.deepcopy((self.manifest, self.policy))
        m, p = provision(self.manifest, self.policy)
        self.assertEqual((self.manifest, self.policy), before)
        self.assertEqual(m["requires"].pop(), REQUIREMENT)
        self.assertEqual(p["grants"].pop(), GRANT)
        self.assertEqual((m, p), before)

    def test_idempotent_and_partial_provisioning(self):
        m, p = provision(self.manifest, self.policy)
        self.assertEqual(provision(m, p), (m, p))
        self.assertEqual(provision(m, self.policy), (m, p))
        self.assertEqual(provision(self.manifest, p), (m, p))

    def test_conflicts_duplicates_and_wrong_app_reject(self):
        for field, value in (("api", 2), ("instance_id", 1)):
            p = copy.deepcopy(self.policy)
            grant = dict(GRANT); grant[field] = value
            p["grants"].append(grant)
            with self.assertRaises(ValueError): provision(self.manifest, p)
        for rows in ([dict(REQUIREMENT, api=2)], [REQUIREMENT, REQUIREMENT]):
            m = copy.deepcopy(self.manifest); m["requires"] += rows
            with self.assertRaises(ValueError): provision(m, self.policy)
        m, p = provision(self.manifest, self.policy)
        p["grants"].append(dict(GRANT))
        with self.assertRaises(ValueError): provision(m, p)
        m = copy.deepcopy(self.manifest); m["optional"].append(dict(REQUIREMENT))
        with self.assertRaises(ValueError): provision(m, self.policy)
        m = dict(self.manifest, file_name="springboard.elf")
        with self.assertRaises(ValueError): provision(m, self.policy)

    def test_capacity_is_checked_before_admission(self):
        for manifest_limit in (True, False):
            m, p = copy.deepcopy((self.manifest, self.policy))
            if manifest_limit:
                m["requires"] *= 31  # Plus one optional and the new requirement.
            else:
                p["grants"] *= 32
            with self.assertRaises(ValueError): provision(m, p)


if __name__ == "__main__":
    unittest.main()
