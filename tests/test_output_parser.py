"""RustScan 输出解析测试。"""

from __future__ import annotations

import unittest

from core.output_parser import parse_open_port_line, parse_rustscan_output


class OutputParserTests(unittest.TestCase):
    def test_parses_greppable_output_with_ansi_and_duplicates(self) -> None:
        output = (
            "\x1b[32m127.0.0.1 -> [443,80,80]\x1b[0m\n"
            "127.0.0.2 -> [22]\n"
            "unrelated diagnostic line\n"
        )

        results = parse_rustscan_output(output)

        self.assertEqual(
            [(item.address, item.port, item.protocol, item.state) for item in results],
            [
                ("127.0.0.1", "80", "tcp", "open"),
                ("127.0.0.1", "443", "tcp", "open"),
                ("127.0.0.2", "22", "tcp", "open"),
            ],
        )

    def test_parses_open_lines_and_uses_requested_protocol(self) -> None:
        output = "Open 192.168.1.1:53\nOpen 192.168.1.1:161\n"

        results = parse_rustscan_output(output, protocol="udp")

        self.assertEqual([item.port for item in results], ["53", "161"])
        self.assertTrue(all(item.protocol == "udp" for item in results))

    def test_parses_single_open_port_line_with_ansi_color(self) -> None:
        result = parse_open_port_line(
            "\x1b[32mOpen 192.168.36.128:2377\x1b[0m",
        )

        self.assertIsNotNone(result)
        self.assertEqual(result.address, "192.168.36.128")
        self.assertEqual(result.port, "2377")
        self.assertEqual(result.protocol, "tcp")
        self.assertEqual(result.state, "open")
        self.assertIsNone(parse_open_port_line("Starting Nmap"))

    def test_parses_nmap_service_version_and_merges_port_only_result(self) -> None:
        output = (
            "Open 127.0.0.1:80\n"
            "[~] Starting Nmap 7.993 ( https://nmap.org )\n"
            "Nmap scan report for localhost (127.0.0.1)\n"
            "PORT   STATE SERVICE REASON          VERSION\n"
            "80/tcp open  http    syn-ack ttl 128 "
            "Apache httpd 2.4.39 ((Win64) OpenSSL/1.1.1b)\n"
        )

        results = parse_rustscan_output(output, target="127.0.0.1")

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].address, "127.0.0.1")
        self.assertEqual(results[0].port, "80")
        self.assertEqual(results[0].protocol, "tcp")
        self.assertEqual(results[0].state, "open")
        self.assertEqual(results[0].service, "http")
        self.assertEqual(
            results[0].version,
            "Apache httpd 2.4.39 ((Win64) OpenSSL/1.1.1b)",
        )


if __name__ == "__main__":
    unittest.main()
