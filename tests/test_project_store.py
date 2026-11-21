"""项目目录服务测试。"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from services.project_store import (
    InvalidNameError,
    NameConflictError,
    ProjectStore,
)


class ProjectStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temp = tempfile.TemporaryDirectory()
        self.store = ProjectStore(Path(self._temp.name))

    def tearDown(self) -> None:
        self._temp.cleanup()

    def test_create_project_uses_default_name_and_deduplicates(self) -> None:
        first = self.store.create_project()
        second = self.store.create_project()

        self.assertEqual(first.name, "新建项目")
        self.assertEqual(second.name, "新建项目2")
        self.assertTrue(first.path.is_dir())
        self.assertTrue(second.path.is_dir())

    def test_create_scan_inside_project_and_deduplicates(self) -> None:
        project = self.store.create_project()
        first = self.store.create_scan(project)
        second = self.store.create_scan(project)

        self.assertEqual(first.name, "新扫描")
        self.assertEqual(second.name, "新扫描2")
        self.assertEqual(first.path.parent, project.path)
        self.assertTrue(first.path.is_dir())
        self.assertTrue(second.path.is_dir())

    def test_create_uses_localized_names(self) -> None:
        project = self.store.create_project("New Project")
        scan = self.store.create_scan(project, "New Scan")

        self.assertEqual(project.name, "New Project")
        self.assertEqual(scan.name, "New Scan")
        self.assertTrue((project.path / "New Scan").is_dir())

    def test_rename_project_moves_folder(self) -> None:
        project = self.store.create_project()
        scan = self.store.create_scan(project)

        renamed = self.store.rename_project(project, "目标系统")

        self.assertEqual(renamed.name, "目标系统")
        self.assertFalse(project.path.exists())
        self.assertTrue(renamed.path.is_dir())
        self.assertTrue((renamed.path / scan.name).is_dir())

    def test_rename_scan_moves_folder(self) -> None:
        project = self.store.create_project()
        scan = self.store.create_scan(project)

        renamed = self.store.rename_scan(scan, "端口扫描")

        self.assertEqual(renamed.name, "端口扫描")
        self.assertFalse(scan.path.exists())
        self.assertTrue(renamed.path.is_dir())

    def test_rename_creates_missing_folder(self) -> None:
        project = self.store.create_project()
        scan = self.store.create_scan(project)
        scan.path.rmdir()

        renamed = self.store.rename_scan(scan, "恢复的扫描")

        self.assertTrue(renamed.path.is_dir())
        self.assertEqual(renamed.path.name, "恢复的扫描")

    def test_rename_rejects_invalid_name(self) -> None:
        project = self.store.create_project()
        with self.assertRaises(InvalidNameError):
            self.store.rename_project(project, "bad/name")

    def test_rename_rejects_existing_name(self) -> None:
        first = self.store.create_project()
        second = self.store.create_project()
        with self.assertRaises(NameConflictError):
            self.store.rename_project(second, first.name)

    def test_delete_scan_without_files_hides_it_but_keeps_folder(self) -> None:
        project = self.store.create_project()
        scan = self.store.create_scan(project)

        self.store.delete_scan(scan, delete_files=False)

        self.assertTrue(scan.path.is_dir())
        projects = self.store.load()
        self.assertEqual(len(projects), 1)
        self.assertEqual(projects[0].scans, [])

    def test_delete_scan_with_files_removes_folder(self) -> None:
        project = self.store.create_project()
        scan = self.store.create_scan(project)
        (scan.path / "result.xml").write_text("<scan_results/>", encoding="utf-8")

        self.store.delete_scan(scan, delete_files=True)

        self.assertFalse(scan.path.exists())
        self.assertEqual(self.store.load()[0].scans, [])

    def test_delete_project_without_files_hides_it_but_keeps_folder(self) -> None:
        project = self.store.create_project()
        self.store.create_scan(project)

        self.store.delete_project(project, delete_files=False)

        self.assertTrue(project.path.is_dir())
        self.assertEqual(self.store.load(), [])

    def test_delete_project_with_files_removes_folder(self) -> None:
        project = self.store.create_project()
        scan = self.store.create_scan(project)
        (scan.path / "result.xml").write_text("<scan_results/>", encoding="utf-8")

        self.store.delete_project(project, delete_files=True)

        self.assertFalse(project.path.exists())
        self.assertEqual(self.store.load(), [])


if __name__ == "__main__":
    unittest.main()
