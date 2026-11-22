"""扫描结果 XML 存取测试。"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from models.result import PortResult
from services.result_store import load_result_documents, save_results
from services.scan_info_store import save_scan_form


class ResultStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temp = tempfile.TemporaryDirectory()
        self.scan_dir = Path(self._temp.name) / "新建项目" / "新扫描"
        self.scan_dir.mkdir(parents=True)

    def tearDown(self) -> None:
        self._temp.cleanup()

    def test_save_and_load_custom_results(self) -> None:
        path = save_results(
            self.scan_dir,
            [
                PortResult("127.0.0.1", "443", "tcp", "open", "https", "nginx"),
                PortResult("127.0.0.1", "80", "tcp", "open", "http", "nginx"),
            ],
            target="127.0.0.1",
        )

        self.assertTrue(path.is_file())
        documents = load_result_documents(self.scan_dir)
        self.assertEqual(len(documents), 1)
        document = documents[0]
        self.assertIsNone(document.error)
        self.assertEqual(document.target, "127.0.0.1")
        self.assertEqual([item.port for item in document.results], ["80", "443"])
        self.assertEqual(document.results[0].service, "http")

    def test_load_nmap_xml(self) -> None:
        xml = '''<?xml version="1.0" encoding="UTF-8"?>
<nmaprun>
  <host>
    <address addr="192.168.1.10" addrtype="ipv4"/>
    <ports>
      <port protocol="tcp" portid="22">
        <state state="open"/>
        <service name="ssh" product="OpenSSH" version="9.6"/>
      </port>
      <port protocol="tcp" portid="80">
        <state state="open"/>
        <service name="http" product="nginx" version="1.24.0"/>
      </port>
    </ports>
  </host>
</nmaprun>
'''
        (self.scan_dir / "nmap.xml").write_text(xml, encoding="utf-8")

        documents = load_result_documents(self.scan_dir)
        self.assertEqual(len(documents), 1)
        document = documents[0]
        self.assertIsNone(document.error)
        self.assertEqual(document.target, "192.168.1.10")
        self.assertEqual(len(document.results), 2)
        self.assertEqual(document.results[0].port, "22")
        self.assertEqual(document.results[0].service, "ssh")
        self.assertEqual(document.results[0].version, "OpenSSH 9.6")

    def test_invalid_xml_returns_error_document(self) -> None:
        (self.scan_dir / "broken.xml").write_text("<scan_results", encoding="utf-8")

        documents = load_result_documents(self.scan_dir)
        self.assertEqual(len(documents), 1)
        self.assertIsNotNone(documents[0].error)
        self.assertEqual(documents[0].results, [])

    def test_job_count_and_legacy_localized_target_are_loaded(self) -> None:
        save_results(
            self.scan_dir,
            [PortResult("127.0.0.1", "80", "tcp", "open", "http", "")],
            target="many targets",
            job_count=4,
            filename="new.xml",
        )
        (self.scan_dir / "legacy.xml").write_text(
            '<?xml version="1.0" encoding="utf-8"?>'
            '<scan_results target="4 组扫描任务">'
            '<result address="127.0.0.1" port="80" protocol="tcp" '
            'state="open" service="http" version="" />'
            "</scan_results>",
            encoding="utf-8",
        )

        documents = {document.path.name: document for document in load_result_documents(self.scan_dir)}

        self.assertEqual(documents["new.xml"].job_count, 4)
        self.assertEqual(documents["legacy.xml"].job_count, 4)

    def test_missing_scan_directory_returns_empty(self) -> None:
        self.assertEqual(load_result_documents(self.scan_dir / "missing"), [])

    def test_scan_info_file_is_not_loaded_as_result(self) -> None:
        save_scan_form(self.scan_dir, {"address": "127.0.0.1"})

        self.assertEqual(load_result_documents(self.scan_dir), [])


if __name__ == "__main__":
    unittest.main()
