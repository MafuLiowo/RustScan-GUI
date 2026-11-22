"""扫描任务规划测试。"""

from __future__ import annotations

import unittest

from core.scan_planner import (
    ATTACK_PITCHFORK,
    ATTACK_SNIPER,
    ScanJob,
    build_scan_jobs,
)


class ScanPlannerTests(unittest.TestCase):
    def test_sniper_uses_all_ports_for_all_addresses(self) -> None:
        jobs = build_scan_jobs(
            ["one.example.com", "two.example.com"],
            imported_ports=[80, 443],
            attack_type=ATTACK_SNIPER,
        )

        self.assertEqual(
            jobs,
            [
                ScanJob(
                    address="one.example.com,two.example.com",
                    ports="80,443",
                )
            ],
        )

    def test_pitchfork_pairs_addresses_and_ports(self) -> None:
        jobs = build_scan_jobs(
            ["one.example.com", "two.example.com"],
            imported_ports=[80, 443],
            attack_type=ATTACK_PITCHFORK,
        )

        self.assertEqual(
            jobs,
            [
                ScanJob(address="one.example.com", ports="80"),
                ScanJob(address="two.example.com", ports="443"),
            ],
        )

    def test_explicit_pairs_are_combined_for_sniper(self) -> None:
        jobs = build_scan_jobs(
            ["one.example.com"],
            pairs=[("one.example.com", 8080), ("two.example.com", 8443)],
            attack_type=ATTACK_SNIPER,
        )

        self.assertEqual(
            jobs,
            [
                ScanJob(
                    address="one.example.com,two.example.com",
                    ports="8080,8443",
                ),
            ],
        )

    def test_explicit_pairs_are_split_for_pitchfork(self) -> None:
        jobs = build_scan_jobs(
            ["one.example.com", "two.example.com"],
            pairs=[("one.example.com", 8080), ("two.example.com", 8443)],
            attack_type=ATTACK_PITCHFORK,
        )

        self.assertEqual(
            jobs,
            [
                ScanJob(address="one.example.com", ports="8080"),
                ScanJob(address="two.example.com", ports="8443"),
            ],
        )

    def test_explicit_pairs_use_unique_ports_for_sniper(self) -> None:
        jobs = build_scan_jobs(
            ["one.example.com"],
            pairs=[
                ("one.example.com", 80),
                ("one.example.com", 80),
                ("two.example.com", 80),
            ],
            attack_type=ATTACK_SNIPER,
        )

        self.assertEqual(
            jobs,
            [
                ScanJob(
                    address="one.example.com,two.example.com",
                    ports="80",
                ),
            ],
        )

    def test_normal_scan_keeps_single_job(self) -> None:
        jobs = build_scan_jobs(
            ["127.0.0.1"],
            port_text="80,443",
        )

        self.assertEqual(
            jobs,
            [ScanJob(address="127.0.0.1", ports="80,443")],
        )


if __name__ == "__main__":
    unittest.main()
