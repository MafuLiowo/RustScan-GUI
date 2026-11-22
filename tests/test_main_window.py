"""主窗口项目管理行为测试（离屏运行）。"""

from __future__ import annotations

import csv
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from config.settings import DEFAULT_NMAP_PATH  # noqa: E402
from PySide6.QtCore import QPoint, QPointF, Qt  # noqa: E402
from PySide6.QtGui import QPalette, QWheelEvent  # noqa: E402
from PySide6.QtWidgets import (  # noqa: E402
    QApplication,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
)

from models.result import PortResult  # noqa: E402
from services.project_store import ProjectStore  # noqa: E402
from services.result_store import load_result_documents, save_results  # noqa: E402
from services.script_store import ScriptStore  # noqa: E402
from ui.main_window import MainWindow  # noqa: E402


class MainWindowProjectTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self._temp = tempfile.TemporaryDirectory()
        self.store = ProjectStore(Path(self._temp.name) / "project")
        self.config_path = Path(self._temp.name) / "config.ini"
        self.script_store = ScriptStore(Path(self._temp.name) / "script")
        self.window = MainWindow(
            store=self.store,
            config_path=self.config_path,
            script_store=self.script_store,
        )

    def tearDown(self) -> None:
        self.window.close()
        self.window.deleteLater()
        self.app.processEvents()
        self._temp.cleanup()

    def test_new_project_and_scan_follow_local_folders(self) -> None:
        self.window._create_project()
        self.assertEqual(self.window._tree.topLevelItemCount(), 1)

        project_item = self.window._tree.topLevelItem(0)
        self.assertEqual(project_item.text(0), "New Project")
        self.assertTrue((self.store.root / "New Project").is_dir())

        self.window._create_scan()
        project_item = self.window._tree.topLevelItem(0)
        self.assertEqual(project_item.childCount(), 1)
        self.assertEqual(project_item.child(0).text(0), "New Scan")
        self.assertTrue((self.store.root / "New Project" / "New Scan").is_dir())

        self.window._create_scan()
        project_item = self.window._tree.topLevelItem(0)
        names = [project_item.child(index).text(0) for index in range(project_item.childCount())]
        self.assertEqual(names, ["New Scan", "New Scan2"])

    def test_rename_project_syncs_tree_and_folder(self) -> None:
        self.window._create_project()
        project_item = self.window._tree.topLevelItem(0)
        self.window._ask_new_name = lambda old_name: ("目标系统", True)

        self.window._rename_item(project_item)

        project_item = self.window._tree.topLevelItem(0)
        self.assertEqual(project_item.text(0), "目标系统")
        self.assertTrue((self.store.root / "目标系统").is_dir())
        self.assertFalse((self.store.root / "New Project").exists())

    def test_rename_scan_syncs_tree_and_folder(self) -> None:
        self.window._create_project()
        self.window._create_scan()
        scan_item = self.window._tree.topLevelItem(0).child(0)
        self.window._ask_new_name = lambda old_name: ("端口扫描", True)

        self.window._rename_item(scan_item)

        project_item = self.window._tree.topLevelItem(0)
        self.assertEqual(project_item.child(0).text(0), "端口扫描")
        self.assertTrue((self.store.root / "New Project" / "端口扫描").is_dir())
        self.assertFalse((self.store.root / "New Project" / "New Scan").exists())

    def test_top_menu_labels(self) -> None:
        labels = [action.text() for action in self.window.menuBar().actions()]
        self.assertEqual(labels, ["File", "Edit", "View", "Scripts", "Help"])

    def test_scripts_menu_opens_manage_page(self) -> None:
        self.script_store.write_script("demo.nse", "print('hello')")
        self.window.show()
        self.app.processEvents()

        scripts_menu = self.window.menuBar().actions()[3].menu()
        actions = {
            action.text(): action
            for action in scripts_menu.actions()
            if action.text()
        }
        self.assertEqual(list(actions), ["Manage Scripts", "Add Script"])

        actions["Manage Scripts"].trigger()
        self.app.processEvents()

        self.assertIs(self.window._stack.currentWidget(), self.window._scripts_page)
        self.assertFalse(self.window._view_sidebar_action.isChecked())
        self.assertFalse(self.window._sidebar.isVisible())
        self.assertEqual(self.window._script_list.count(), 1)
        self.assertEqual(self.window._script_list.item(0).text(), "demo.nse")
        self.assertEqual(self.window._script_content.toPlainText(), "print('hello')")

    def test_add_script_dialog_uses_green_confirm_button(self) -> None:
        dialog, name_edit, content_edit, confirm = (
            self.window._build_add_script_dialog()
        )

        self.assertEqual(dialog.windowTitle(), "Add Script")
        self.assertEqual(confirm.objectName(), "SuccessButton")
        self.assertEqual(confirm.text(), "Confirm")
        self.assertFalse(confirm.isEnabled())
        self.assertEqual(
            content_edit.placeholderText(),
            "Enter script content here.",
        )

        name_edit.setText("demo.nse")
        self.assertTrue(confirm.isEnabled())

    def test_add_script_dialog_saves_script_file(self) -> None:
        def fake_exec(dialog) -> int:
            name_edit = dialog.findChild(QLineEdit)
            content_edit = dialog.findChild(QPlainTextEdit, "ScriptEditor")
            confirm = dialog.findChild(QPushButton, "SuccessButton")
            name_edit.setText("saved.nse")
            content_edit.setPlainText("saved content")
            confirm.click()
            return 0

        with patch("ui.main_window.QDialog.exec", fake_exec):
            self.window._show_add_script_dialog()

        path = self.script_store.root / "saved.nse"
        self.assertTrue(path.is_file())
        self.assertEqual(path.read_text(encoding="utf-8"), "saved content")
        self.assertEqual(self.window._script_list.count(), 1)
        self.assertEqual(self.window._script_content.toPlainText(), "saved content")

    def test_script_context_menu_opens_script_location(self) -> None:
        self.script_store.write_script("demo.nse", "demo")
        self.window._refresh_script_list()
        item = self.window._script_list.item(0)

        menu = self.window._build_script_context_menu(item)
        actions = [action.text() for action in menu.actions() if action.text()]
        self.assertEqual(actions, ["Open in Explorer", "Delete Script"])

        with patch.object(self.window, "_open_script_in_explorer") as opener:
            menu.actions()[0].trigger()
        opener.assert_called_once_with("demo.nse")

        with patch(
            "ui.main_window.QDesktopServices.openUrl",
            return_value=True,
        ) as open_url:
            self.window._open_script_in_explorer("demo.nse")

        folder = Path(open_url.call_args.args[0].toLocalFile())
        self.assertEqual(folder, self.script_store.root)

    def test_script_context_menu_deletes_script_file(self) -> None:
        self.script_store.write_script("demo.nse", "demo")
        self.window._refresh_script_list()
        item = self.window._script_list.item(0)
        menu = self.window._build_script_context_menu(item)
        delete_action = next(
            action for action in menu.actions() if action.text() == "Delete Script"
        )

        with patch(
            "ui.main_window.QMessageBox.question",
            return_value=QMessageBox.StandardButton.Yes,
        ):
            delete_action.trigger()

        self.assertFalse((self.script_store.root / "demo.nse").exists())
        self.assertEqual(self.window._script_list.count(), 0)
        self.assertEqual(self.window._script_content.toPlainText(), "")

    def test_window_title_and_about_logo(self) -> None:
        self.assertEqual(
            self.window.windowTitle(),
            "RustScan-GUI by MafuLiowo",
        )
        dialog = self.window._build_about_dialog()
        logo = dialog.findChild(QLabel, "AboutLogo")
        self.assertIsNotNone(logo)
        self.assertFalse(logo.pixmap().isNull())

        description = dialog.findChild(QLabel, "AboutDescription")
        github_icon = dialog.findChild(QLabel, "AboutGitHubIcon")
        github_link = dialog.findChild(QLabel, "AboutGitHubLink")
        self.assertIsNotNone(description)
        self.assertIsNotNone(github_icon)
        self.assertIsNotNone(github_link)
        self.assertEqual(github_icon.height(), description.fontMetrics().height())
        self.assertFalse(github_icon.pixmap().isNull())
        self.assertTrue(github_link.openExternalLinks())
        self.assertIn("https://github.com/MafuLiowo", github_link.text())
        dialog.deleteLater()

    def test_delete_dialog_uses_checkbox_and_red_confirm(self) -> None:
        self.window._create_project()
        self.window._create_scan()
        scan_item = self.window._tree.topLevelItem(0).child(0)

        dialog, checkbox = self.window._build_delete_dialog(scan_item)
        confirm = dialog.findChild(QPushButton, "DangerButton")

        self.assertEqual(dialog.windowTitle(), "Delete?")
        self.assertEqual(checkbox.text(), "Also delete local files")
        self.assertFalse(checkbox.isChecked())
        self.assertIsNotNone(confirm)
        self.assertEqual(confirm.text(), "Confirm")
        dialog.deleteLater()

    def test_delete_scan_without_local_files_only_hides_it(self) -> None:
        self.window._create_project()
        self.window._create_scan()
        project_item = self.window._tree.topLevelItem(0)
        scan_item = project_item.child(0)
        scan_path = self.store.root / "New Project" / "New Scan"
        self.window._confirm_delete = lambda _item: False

        self.window._delete_item(scan_item)

        project_item = self.window._tree.topLevelItem(0)
        self.assertEqual(project_item.childCount(), 0)
        self.assertTrue(scan_path.is_dir())
        self.assertEqual(self.store.load()[0].scans, [])

    def test_delete_scan_with_local_files_removes_directory(self) -> None:
        self.window._create_project()
        self.window._create_scan()
        scan_item = self.window._tree.topLevelItem(0).child(0)
        scan_path = self.store.root / "New Project" / "New Scan"
        self.window._confirm_delete = lambda _item: True

        self.window._delete_item(scan_item)

        self.assertFalse(scan_path.exists())
        self.assertEqual(self.window._tree.topLevelItem(0).childCount(), 0)

    def test_edit_menu_settings_switches_to_settings_page(self) -> None:
        self.window._create_project()
        self.window._create_scan()
        self.window.show()
        self.app.processEvents()
        self.assertTrue(self.window._sidebar.isVisible())

        edit_menu = self.window.menuBar().actions()[1].menu()
        actions = {action.text(): action for action in edit_menu.actions() if action.text()}

        self.assertIn("Settings", actions)
        actions["Settings"].trigger()
        self.app.processEvents()

        self.assertIs(self.window._stack.currentWidget(), self.window._settings_page)
        self.assertFalse(self.window._view_sidebar_action.isChecked())
        self.assertFalse(self.window._sidebar.isVisible())
        self.assertEqual(self.window._language_combo.currentText(), "English")
        self.assertEqual(
            [self.window._language_combo.itemText(index) for index in range(2)],
            ["English", "简体中文"],
        )
        labels = [
            label.text() for label in self.window._settings_page.findChildren(QLabel)
        ]
        self.assertIn("Language", labels)
        self.assertIn("Language Settings", labels)

        actions["Main Interface"].trigger()
        self.app.processEvents()

        self.assertTrue(self.window._view_sidebar_action.isChecked())
        self.assertTrue(self.window._sidebar.isVisible())
        self.assertIs(self.window._stack.currentWidget(), self.window._scan_page)

    def test_switching_to_simplified_chinese_retranslates_ui(self) -> None:
        edit_menu = self.window.menuBar().actions()[1].menu()
        settings_action = next(
            action for action in edit_menu.actions() if action.text() == "Settings"
        )
        settings_action.trigger()
        self.app.processEvents()

        index = self.window._language_combo.findData("zh_CN")
        self.window._language_combo.setCurrentIndex(index)
        self.app.processEvents()

        self.assertEqual(self.window._language_store.current_code, "zh_CN")
        self.assertEqual(
            self.config_path.read_text(encoding="utf-8"),
            'language = "zh_CN"\n'
            f'nmap_path = "{DEFAULT_NMAP_PATH}"\n',
        )
        self.assertIs(self.window._stack.currentWidget(), self.window._settings_page)
        self.assertEqual(self.window._language_combo.currentText(), "简体中文")
        labels = [action.text() for action in self.window.menuBar().actions()]
        self.assertEqual(labels, ["文件", "编辑", "视图", "脚本", "帮助"])

        self.window._create_project()
        self.window._create_scan()
        project_item = self.window._tree.topLevelItem(0)
        self.assertEqual(project_item.text(0), "新建项目")
        self.assertEqual(project_item.child(0).text(0), "新扫描")
        self.assertTrue((self.store.root / "新建项目" / "新扫描").is_dir())
        self.assertEqual(
            [
                self.window._attack_type_combo.itemText(index)
                for index in range(self.window._attack_type_combo.count())
            ],
            ["Sniper扫描", "Pitchfork扫描"],
        )
        self.assertEqual(self.window._export_csv_button.text(), "导出为CSV格式")

    def test_interface_settings_switches_display_mode(self) -> None:
        self.window._show_settings_page()
        self.window._settings_nav_group.button(1).click()
        self.app.processEvents()

        self.assertEqual(self.window._settings_stack.currentIndex(), 1)
        self.assertEqual(
            self.window._settings_nav_group.button(1).text(),
            "Interface",
        )
        labels = [label.text() for label in self.window._settings_page.findChildren(QLabel)]
        self.assertIn("Interface Settings", labels)
        self.assertIn("Display mode", labels)
        self.assertEqual(
            [
                self.window._display_mode_combo.itemText(index)
                for index in range(self.window._display_mode_combo.count())
            ],
            ["Day", "Night", "Follow System"],
        )
        self.assertEqual(self.window._display_mode_combo.currentData(), "dark")

        day_index = self.window._display_mode_combo.findData("light")
        self.window._display_mode_combo.setCurrentIndex(day_index)
        self.app.processEvents()
        self.assertGreater(
            self.app.palette().color(QPalette.ColorRole.Window).lightness(),
            128,
        )

        language_index = self.window._language_combo.findData("zh_CN")
        self.window._language_combo.setCurrentIndex(language_index)
        self.app.processEvents()
        self.assertEqual(self.window._settings_stack.currentIndex(), 1)
        self.assertEqual(self.window._settings_nav_group.button(1).text(), "界面")
        self.assertEqual(
            [
                self.window._display_mode_combo.itemText(index)
                for index in range(self.window._display_mode_combo.count())
            ],
            ["日间", "夜间", "跟随系统"],
        )
        self.assertIn(
            'display_mode = "light"',
            self.config_path.read_text(encoding="utf-8"),
        )

        with patch("utils.theme.system_prefers_dark", return_value=True):
            system_index = self.window._display_mode_combo.findData("system")
            self.window._display_mode_combo.setCurrentIndex(system_index)
            self.app.processEvents()
        self.assertLess(
            self.app.palette().color(QPalette.ColorRole.Window).lightness(),
            128,
        )
        self.assertIn(
            'display_mode = "system"',
            self.config_path.read_text(encoding="utf-8"),
        )

        with patch("utils.theme.system_prefers_dark", return_value=False):
            self.window._on_system_color_scheme_changed()
            self.app.processEvents()
        self.assertGreater(
            self.app.palette().color(QPalette.ColorRole.Window).lightness(),
            128,
        )

    def test_nmap_support_settings_persist_path(self) -> None:
        self.window._show_settings_page()
        self.window._settings_nav_group.button(2).click()
        self.app.processEvents()

        self.assertEqual(self.window._settings_stack.currentIndex(), 2)
        self.assertEqual(
            self.window._settings_nav_group.button(2).text(),
            "Nmap Support",
        )
        labels = [
            label.text() for label in self.window._settings_page.findChildren(QLabel)
        ]
        self.assertIn("Nmap path", labels)
        self.assertEqual(self.window._nmap_path_edit.text(), DEFAULT_NMAP_PATH)

        nmap_path = r"D:\Tools\Nmap\nmap.exe"
        self.window._nmap_path_edit.setText(nmap_path)
        with patch.object(self.window._runner, "set_nmap_path") as setter:
            self.window._nmap_path_edit.editingFinished.emit()
        setter.assert_called_once_with(nmap_path)
        self.assertEqual(self.window._nmap_path, nmap_path)
        self.assertIn(
            f'nmap_path = "{nmap_path}"',
            self.config_path.read_text(encoding="utf-8"),
        )

        language_index = self.window._language_combo.findData("zh_CN")
        self.window._language_combo.setCurrentIndex(language_index)
        self.app.processEvents()
        self.assertEqual(
            self.window._settings_nav_group.button(2).text(),
            "Nmap支持",
        )
        self.assertEqual(self.window._nmap_path_edit.text(), nmap_path)

        self.window.close()
        self.window.deleteLater()
        self.app.processEvents()
        self.window = MainWindow(
            store=self.store,
            config_path=self.config_path,
            script_store=self.script_store,
        )

        self.assertEqual(self.window._nmap_path, nmap_path)
        self.assertEqual(self.window._nmap_path_edit.text(), nmap_path)

    def test_startup_reads_saved_display_mode(self) -> None:
        self.window.close()
        self.window.deleteLater()
        self.app.processEvents()
        self.config_path.write_text(
            'language = "en"\ndisplay_mode = "light"\n',
            encoding="utf-8",
        )

        self.window = MainWindow(
            store=self.store,
            config_path=self.config_path,
            script_store=self.script_store,
        )

        self.assertEqual(self.window._display_mode, "light")
        self.assertEqual(self.window._display_mode_combo.currentData(), "light")
        self.assertGreater(
            self.app.palette().color(QPalette.ColorRole.Window).lightness(),
            128,
        )

    def test_startup_creates_config_and_reads_saved_language(self) -> None:
        self.assertEqual(
            self.config_path.read_text(encoding="utf-8"),
            'language = "en"\n'
            f'nmap_path = "{DEFAULT_NMAP_PATH}"\n',
        )

        self.window.close()
        self.window.deleteLater()
        self.app.processEvents()
        self.config_path.write_text('language = "zh_CN"\n', encoding="utf-8")
        self.window = MainWindow(
            store=self.store,
            config_path=self.config_path,
            script_store=self.script_store,
        )

        self.assertEqual(self.window._language_store.current_code, "zh_CN")
        labels = [action.text() for action in self.window.menuBar().actions()]
        self.assertEqual(labels, ["文件", "编辑", "视图", "脚本", "帮助"])

    def test_language_switch_preserves_scan_form_values(self) -> None:
        self.window._create_project()
        self.window._create_scan()
        self.window._address_edit.setText("10.0.0.0/24")
        self.window._port_mode.setCurrentText("Range")
        self.window._ports_edit.setText("80-8080")
        self.window._exclude_ip_mode.setCurrentText("Yes")
        self.window._exclude_ip_edit.setText("10.0.0.8")
        self.window._ignore_config_combo.setCurrentText("Yes")

        self.window._show_settings_page()
        index = self.window._language_combo.findData("zh_CN")
        self.window._language_combo.setCurrentIndex(index)
        self.app.processEvents()

        scan_item = self.window._tree.topLevelItem(0).child(0)
        self.window._on_tree_item_clicked(scan_item, 0)
        self.app.processEvents()

        self.assertIs(self.window._stack.currentWidget(), self.window._scan_page)
        self.assertEqual(
            [self.window._tabs.tabText(index) for index in range(3)],
            ["扫描选项", "扫描结果", "日志"],
        )
        self.assertEqual(self.window._start_button.text(), "开始扫描")
        self.assertEqual(self.window._address_edit.text(), "10.0.0.0/24")
        self.assertEqual(self.window._port_mode.currentData(), "range")
        self.assertEqual(self.window._ports_edit.text(), "80-8080")
        self.assertEqual(self.window._exclude_ip_mode.currentText(), "是")
        self.assertEqual(self.window._exclude_ip_edit.text(), "10.0.0.8")
        self.assertTrue(self.window._exclude_ip_edit.isEnabled())
        self.assertEqual(self.window._ignore_config_combo.currentText(), "是")

    def test_file_menu_actions_create_project_and_scan(self) -> None:
        file_menu = self.window.menuBar().actions()[0].menu()
        actions = {action.text(): action for action in file_menu.actions() if action.text()}

        actions["New Project"].trigger()
        actions["New Scan"].trigger()

        project_item = self.window._tree.topLevelItem(0)
        self.assertEqual(project_item.text(0), "New Project")
        self.assertEqual(project_item.child(0).text(0), "New Scan")
        self.assertTrue((self.store.root / "New Project" / "New Scan").is_dir())

    def test_scan_item_opens_scan_page_with_tabs(self) -> None:
        self.window._create_project()
        self.window._create_scan()

        self.assertIs(self.window._stack.currentWidget(), self.window._scan_page)
        self.assertEqual(self.window._scan_title.text(), "New Scan")
        tabs = [
            self.window._tabs.tabText(index)
            for index in range(self.window._tabs.count())
        ]
        self.assertEqual(tabs, ["Scan Options", "Scan Results", "Logs"])
        labels = [label.text() for label in self.window._scan_page.findChildren(QLabel)]
        self.assertIn("Scan address (domain, CIDR, IP)", labels)
        self.assertIn("*", labels)
        self.assertIn("Add excluded IP addresses?", labels)
        self.assertIn("Add excluded ports?", labels)
        self.assertIn("Ignore configuration file?", labels)
        self.assertIn("Use UDP mode?", labels)

    def test_logs_tab_streams_scan_output_and_survives_language_change(self) -> None:
        self.window._create_project()
        self.window._create_scan()

        self.assertTrue(self.window._log_view.isReadOnly())
        self.window._runner.outputReceived.emit("line one\nline tw")
        self.window._runner.outputReceived.emit("o\nOpen 127.0.0.1:80\n")
        self.app.processEvents()

        text = self.window._log_view.toPlainText()
        self.assertIn("Application started", text)
        self.assertIn("Created", text)
        self.assertIn("line one", text)
        self.assertIn("line two", text)
        self.assertIn("Open 127.0.0.1:80", text)
        self.assertIn("SCAN", text)

        self.window._show_settings_page()
        language_index = self.window._language_combo.findData("zh_CN")
        self.window._language_combo.setCurrentIndex(language_index)
        self.app.processEvents()

        text = self.window._log_view.toPlainText()
        self.assertIn("line one", text)
        self.assertIn("line two", text)
        self.assertEqual(
            [self.window._tabs.tabText(index) for index in range(3)],
            ["扫描选项", "扫描结果", "日志"],
        )

    def test_port_mode_updates_placeholder(self) -> None:
        self.window._create_project()
        self.window._create_scan()

        self.assertEqual(
            self.window._ports_edit.placeholderText(),
            "Ports (comma separated, e.g. 80,8080)",
        )
        self.window._port_mode.setCurrentText("Range")
        self.assertEqual(
            self.window._ports_edit.placeholderText(),
            "Range, e.g. 80-8080",
        )
        self.window._port_mode.setCurrentText("Ports")
        self.assertEqual(
            self.window._ports_edit.placeholderText(),
            "Ports (comma separated, e.g. 80,8080)",
        )

    def test_scan_options_page_scrolls_with_mouse_wheel(self) -> None:
        self.window._create_project()
        self.window._create_scan()
        self.window.setMinimumSize(0, 0)
        self.window.resize(900, 360)
        self.window.show()
        self.app.processEvents()

        scroll_area = self.window._scan_options_scroll
        scrollbar = scroll_area.verticalScrollBar()
        self.assertGreater(scrollbar.maximum(), 0)

        before = scrollbar.value()
        wheel = QWheelEvent(
            QPointF(100, 50),
            QPointF(100, 50),
            QPoint(0, 0),
            QPoint(0, -120),
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier,
            Qt.ScrollPhase.ScrollUpdate,
            False,
        )
        QApplication.sendEvent(scroll_area.viewport(), wheel)
        self.app.processEvents()

        self.assertGreater(scrollbar.value(), before)

    def test_boolean_options_default_to_no_and_exclude_input_toggles(self) -> None:
        self.window._create_project()
        self.window._create_scan()

        for combo in (
            self.window._address_file_mode,
            self.window._ignore_config_combo,
            self.window._udp_mode_combo,
            self.window._nmap_version_combo,
            self.window._exclude_ip_mode,
            self.window._exclude_mode,
            self.window._use_script_combo,
        ):
            self.assertEqual(combo.currentText(), "No")
            self.assertEqual(
                [combo.itemText(index) for index in range(combo.count())],
                ["Yes", "No"],
            )

        self.assertEqual(
            self.window._address_file_edit.placeholderText(),
            "Address file location",
        )
        self.assertFalse(self.window._address_file_edit.isEnabled())
        self.assertFalse(self.window._address_file_button.isEnabled())
        self.window._address_file_mode.setCurrentText("Yes")
        self.assertTrue(self.window._address_file_edit.isEnabled())
        self.assertTrue(self.window._address_file_button.isEnabled())

        self.assertFalse(self.window._exclude_ip_edit.isEnabled())
        self.window._exclude_ip_mode.setCurrentText("Yes")
        self.assertTrue(self.window._exclude_ip_edit.isEnabled())
        self.window._exclude_ip_edit.setText("192.168.1.5")
        self.window._exclude_ip_mode.setCurrentText("No")
        self.assertFalse(self.window._exclude_ip_edit.isEnabled())

        self.assertFalse(self.window._exclude_ports_edit.isEnabled())
        self.window._exclude_mode.setCurrentText("Yes")
        self.assertTrue(self.window._exclude_ports_edit.isEnabled())
        self.window._exclude_ports_edit.setText("22,3389")
        self.window._exclude_mode.setCurrentText("No")
        self.assertFalse(self.window._exclude_ports_edit.isEnabled())

        self.assertFalse(self.window._nmap_extra_args_edit.isEnabled())
        self.assertEqual(
            self.window._nmap_extra_args_edit.placeholderText(),
            "Additional Nmap scan arguments",
        )
        self.window._nmap_version_combo.setCurrentText("Yes")
        self.assertTrue(self.window._nmap_extra_args_edit.isEnabled())
        self.window._nmap_version_combo.setCurrentText("No")
        self.assertFalse(self.window._nmap_extra_args_edit.isEnabled())
        self.assertFalse(self.window._scan_script_combo.isEnabled())

    def test_choose_address_file_loads_txt_targets(self) -> None:
        targets = Path(self._temp.name) / "targets.txt"
        targets.write_text(
            "127.0.0.1\nexample.com\n",
            encoding="utf-8",
        )
        self.window._create_project()
        self.window._create_scan()
        self.window._address_file_mode.setCurrentText("Yes")

        with patch(
            "ui.main_window.QFileDialog.getOpenFileName",
            return_value=(str(targets), ""),
        ) as dialog:
            self.window._choose_address_file()

        dialog.assert_called_once()
        self.assertEqual(dialog.call_args.args[1], "Select Address File")
        self.assertEqual(
            dialog.call_args.args[3],
            "Address files (*.txt *.csv);;Text files (*.txt);;CSV files (*.csv)",
        )
        self.assertEqual(self.window._address_file_edit.text(), str(targets))
        self.assertIn(
            "Imported 2 addresses from targets.txt",
            [entry[2] for entry in self.window._log_entries],
        )

    def test_start_scan_uses_addresses_from_imported_csv(self) -> None:
        targets = Path(self._temp.name) / "targets.csv"
        targets.write_text(
            "name,ip,domain\n"
            "first,192.168.1.10,one.example.com\n"
            "second,192.168.1.11,two.example.com\n",
            encoding="utf-8",
        )
        self.window._create_project()
        self.window._create_scan()
        submitted: dict[str, object] = {}

        def fake_start(program, arguments, working_directory) -> None:
            submitted["arguments"] = arguments

        self.window._runner.start = fake_start
        self.window._address_edit.clear()
        self.window._address_file_mode.setCurrentText("Yes")
        self.window._address_file_edit.setText(str(targets))
        self.window._ports_edit.setText("80")

        self.window._start_scan()

        self.assertEqual(
            submitted["arguments"],
            [
                "-a",
                "192.168.1.10,one.example.com,192.168.1.11,two.example.com",
                "-p",
                "80",
                "-g",
                "--no-banner",
            ],
        )

    def test_address_import_disables_manual_address_input(self) -> None:
        self.window._create_project()
        self.window._create_scan()

        self.assertTrue(self.window._address_edit.isEnabled())
        self.window._address_file_mode.setCurrentText("Yes")

        self.assertFalse(self.window._address_edit.isEnabled())
        self.assertTrue(self.window._address_file_edit.isEnabled())
        labels = [label.text() for label in self.window._scan_page.findChildren(QLabel)]
        self.assertIn("Import addresses from file (txt, csv)", labels)

        self.window._address_file_mode.setCurrentText("No")
        self.assertTrue(self.window._address_edit.isEnabled())
        self.assertFalse(self.window._address_file_edit.isEnabled())

    def test_port_file_mode_selects_and_loads_ports(self) -> None:
        ports = Path(self._temp.name) / "ports.csv"
        ports.write_text("port\n80\n443\n70000\n", encoding="utf-8")
        self.window._create_project()
        self.window._create_scan()
        self.assertIn("File Import", [
            self.window._port_mode.itemText(index)
            for index in range(self.window._port_mode.count())
        ])

        self.window._port_mode.setCurrentText("File Import")
        self.assertTrue(self.window._ports_file_button.isEnabled())
        self.assertEqual(
            self.window._ports_edit.placeholderText(),
            "Port file location (0-65535)",
        )

        with patch(
            "ui.main_window.QFileDialog.getOpenFileName",
            return_value=(str(ports), ""),
        ) as dialog:
            self.window._choose_port_file()

        dialog.assert_called_once()
        self.assertEqual(dialog.call_args.args[1], "Select Port File")
        self.assertEqual(
            dialog.call_args.args[3],
            "Port files (*.txt *.csv);;Text files (*.txt);;CSV files (*.csv)",
        )
        self.assertEqual(self.window._ports_edit.text(), str(ports))
        self.assertIn(
            "Imported 2 ports from ports.csv",
            [entry[2] for entry in self.window._log_entries],
        )

        self.window._port_mode.setCurrentText("Range")
        self.assertFalse(self.window._ports_file_button.isEnabled())
        self.assertEqual(
            self.window._ports_edit.placeholderText(),
            "Range, e.g. 80-8080",
        )

    def test_attack_type_is_visible_only_for_two_imported_files(self) -> None:
        self.window._create_project()
        self.window._create_scan()

        self.assertTrue(self.window._attack_type_widget.isHidden())
        self.window._address_file_mode.setCurrentText("Yes")
        self.assertTrue(self.window._attack_type_widget.isHidden())
        self.window._port_mode.setCurrentText("File Import")
        self.assertFalse(self.window._attack_type_widget.isHidden())
        self.assertEqual(
            self.window._attack_type_combo.currentData(),
            "sniper",
        )
        self.assertEqual(
            [
                self.window._attack_type_combo.itemText(index)
                for index in range(self.window._attack_type_combo.count())
            ],
            ["Sniper Scan", "Pitchfork Scan"],
        )
        self.window._port_mode.setCurrentText("Ports")
        self.assertTrue(self.window._attack_type_widget.isHidden())

    def test_address_file_with_ports_switches_to_pitchfork(self) -> None:
        targets = Path(self._temp.name) / "paired.csv"
        targets.write_text(
            "domain,port\n"
            "one.example.com,80\n"
            "two.example.com,443\n",
            encoding="utf-8",
        )
        self.window._create_project()
        self.window._create_scan()
        self.window._address_file_mode.setCurrentText("Yes")

        with patch(
            "ui.main_window.QFileDialog.getOpenFileName",
            return_value=(str(targets), ""),
        ):
            self.window._choose_address_file()

        self.assertEqual(self.window._port_mode.currentData(), "file")
        self.assertEqual(self.window._ports_edit.text(), str(targets))
        self.assertEqual(self.window._attack_type_combo.currentData(), "pitchfork")
        self.assertFalse(self.window._attack_type_widget.isHidden())
        self.assertTrue(self.window._ports_file_button.isEnabled())

    def test_paired_address_file_can_be_changed_to_sniper(self) -> None:
        targets = Path(self._temp.name) / "paired.csv"
        targets.write_text(
            "domain,port\n"
            "one.example.com,80\n"
            "two.example.com,443\n",
            encoding="utf-8",
        )
        self.window._create_project()
        self.window._create_scan()
        submitted: dict[str, object] = {}

        def fake_start(program, arguments, working_directory) -> None:
            submitted["arguments"] = arguments

        self.window._runner.start = fake_start
        self.window._address_file_mode.setCurrentText("Yes")
        with patch(
            "ui.main_window.QFileDialog.getOpenFileName",
            return_value=(str(targets), ""),
        ):
            self.window._choose_address_file()
        self.window._attack_type_combo.setCurrentIndex(
            self.window._attack_type_combo.findData("sniper")
        )

        self.window._start_scan()

        self.assertEqual(
            submitted["arguments"],
            [
                "-a",
                "one.example.com,two.example.com",
                "-p",
                "80,443",
                "-g",
                "--no-banner",
            ],
        )
        self.assertEqual(
            self.window._attack_type_combo.currentData(),
            "sniper",
        )

    def test_two_imported_files_can_run_sniper_attack(self) -> None:
        targets = Path(self._temp.name) / "targets.txt"
        targets.write_text("one.example.com\ntwo.example.com\n", encoding="utf-8")
        ports = Path(self._temp.name) / "ports.txt"
        ports.write_text("80\n443\n", encoding="utf-8")
        self.window._create_project()
        self.window._create_scan()
        submitted: dict[str, object] = {}

        def fake_start(program, arguments, working_directory) -> None:
            submitted["arguments"] = arguments

        self.window._runner.start = fake_start
        self.window._address_file_mode.setCurrentText("Yes")
        self.window._address_file_edit.setText(str(targets))
        self.window._port_mode.setCurrentText("File Import")
        self.window._ports_edit.setText(str(ports))
        self.window._attack_type_combo.setCurrentIndex(
            self.window._attack_type_combo.findData("sniper")
        )

        self.window._start_scan()

        self.assertEqual(
            submitted["arguments"],
            [
                "-a",
                "one.example.com,two.example.com",
                "-p",
                "80,443",
                "-g",
                "--no-banner",
            ],
        )
        self.assertEqual(len(self.window._scan_jobs), 1)

    def test_two_imported_files_can_run_pitchfork_attack(self) -> None:
        targets = Path(self._temp.name) / "targets.txt"
        targets.write_text("one.example.com\ntwo.example.com\n", encoding="utf-8")
        ports = Path(self._temp.name) / "ports.txt"
        ports.write_text("80\n443\n", encoding="utf-8")
        self.window._create_project()
        self.window._create_scan()
        scan_path = self.store.root / "New Project" / "New Scan"
        submitted: list[list[str]] = []

        def fake_start(program, arguments, working_directory) -> None:
            submitted.append(arguments)

        self.window._runner.start = fake_start
        self.window._address_file_mode.setCurrentText("Yes")
        self.window._address_file_edit.setText(str(targets))
        self.window._port_mode.setCurrentText("File Import")
        self.window._ports_edit.setText(str(ports))
        self.window._attack_type_combo.setCurrentIndex(
            self.window._attack_type_combo.findData("pitchfork")
        )

        self.window._start_scan()

        self.assertEqual(
            submitted,
            [["-a", "one.example.com", "-p", "80", "-g", "--no-banner"]],
        )
        self.assertEqual(len(self.window._scan_jobs), 2)

        with patch("ui.main_window.QMessageBox.information"):
            self.window._on_scan_finished(
                0,
                "one.example.com -> [80]\n",
                "",
            )
            self.assertEqual(
                submitted[-1],
                ["-a", "two.example.com", "-p", "443", "-g", "--no-banner"],
            )
            self.window._on_scan_finished(
                0,
                "two.example.com -> [443]\n",
                "",
            )

        result_files = list(scan_path.glob("result-*.xml"))
        self.assertEqual(len(result_files), 1)
        self.assertEqual(self.window._result_table.rowCount(), 2)
        self.assertEqual(
            [self.window._result_table.item(row, 0).text() for row in range(2)],
            ["one.example.com", "two.example.com"],
        )

    def test_multi_job_target_uses_current_interface_language(self) -> None:
        self.window._create_project()
        self.window._create_scan()
        scan = self.store.load()[0].scans[0]
        save_results(
            scan.path,
            [PortResult("one.example.com", "80", "tcp", "open", "http", "")],
            target="4 组扫描任务",
            job_count=4,
            filename="result-2026-11-22-14-30-00.xml",
        )

        self.window._show_scan_page(scan)
        self.window._tabs.setCurrentIndex(1)
        self.app.processEvents()

        self.assertIn("Target: 4 scan jobs", self.window._result_hint.text())
        self.assertNotIn("组扫描任务", self.window._result_hint.text())

    def test_start_scan_button_is_configured(self) -> None:
        self.window._create_project()
        self.window._create_scan()

        self.assertEqual(self.window._start_button.text(), "Start Scan")
        self.assertEqual(self.window._start_button.objectName(), "StartScanButton")
        self.assertTrue(self.window._start_button.isEnabled())

    def test_start_scan_runs_rustscan_and_saves_results_in_scan_folder(self) -> None:
        self.window._create_project()
        self.window._create_scan()
        scan_path = self.store.root / "New Project" / "New Scan"
        submitted: dict[str, object] = {}

        self.window._tabs.setCurrentIndex(1)
        self.app.processEvents()
        self.window._tabs.setCurrentIndex(0)
        self.app.processEvents()

        def fake_start(program, arguments, working_directory) -> None:
            submitted["program"] = program
            submitted["arguments"] = arguments
            submitted["working_directory"] = working_directory

        self.window._runner.start = fake_start
        self.window._address_edit.setText("127.0.0.1")
        self.window._port_mode.setCurrentText("Range")
        self.window._ports_edit.setText("1-1024")
        self.window._exclude_ip_mode.setCurrentText("Yes")
        self.window._exclude_ip_edit.setText("127.0.0.2")
        self.window._exclude_mode.setCurrentText("Yes")
        self.window._exclude_ports_edit.setText("22")
        self.window._ignore_config_combo.setCurrentText("Yes")

        self.window._start_scan()

        self.assertEqual(
            submitted["arguments"],
            [
                "-a",
                "127.0.0.1",
                "-r",
                "1-1024",
                "-x",
                "127.0.0.2",
                "-e",
                "22",
                "-n",
                "-g",
                "--no-banner",
            ],
        )
        self.assertEqual(submitted["working_directory"], scan_path)
        self.assertFalse(self.window._start_button.isEnabled())

        with patch("ui.main_window.QMessageBox.information"):
            self.window._on_scan_finished(
                0,
                "127.0.0.1 -> [443,80,80]\n",
                "",
            )

        result_files = list(scan_path.glob("result-*.xml"))
        self.assertEqual(len(result_files), 1)
        self.assertRegex(
            result_files[0].name,
            r"^result-\d{4}-\d{2}-\d{2}-\d{2}-\d{2}-\d{2}\.xml$",
        )
        self.assertTrue(result_files[0].is_file())
        self.assertEqual(self.window._tabs.currentIndex(), 1)
        self.assertEqual(self.window._result_table.rowCount(), 2)
        self.assertTrue(self.window._start_button.isEnabled())

    def test_start_scan_uses_nmap_version_switch(self) -> None:
        self.window._create_project()
        self.window._create_scan()
        submitted: dict[str, object] = {}

        def fake_start(program, arguments, working_directory) -> None:
            submitted["arguments"] = arguments

        self.window._runner.start = fake_start
        self.window._address_edit.setText("127.0.0.1")
        self.window._ports_edit.setText("80")
        self.window._nmap_version_combo.setCurrentText("Yes")
        self.window._nmap_extra_args_edit.setText("-sC")

        self.window._start_scan()

        self.assertEqual(
            submitted["arguments"],
            ["-a", "127.0.0.1", "-p", "80", "--no-banner", "--", "-sV", "-sC"],
        )

    def test_scan_script_selector_uses_scripts_from_script_folder(self) -> None:
        self.script_store.write_script("demo.nse", "print('demo')")
        self.window._create_project()
        self.window._create_scan()
        submitted: dict[str, object] = {}

        def fake_start(program, arguments, working_directory) -> None:
            submitted["arguments"] = arguments

        self.window._runner.start = fake_start
        self.assertEqual(self.window._use_script_combo.currentText(), "No")
        self.assertFalse(self.window._scan_script_combo.isEnabled())
        self.assertEqual(self.window._scan_script_combo.currentData(), "demo.nse")

        self.window._use_script_combo.setCurrentText("Yes")
        self.assertTrue(self.window._scan_script_combo.isEnabled())
        self.window._address_edit.setText("127.0.0.1")
        self.window._ports_edit.setText("80")
        self.window._start_scan()

        self.assertEqual(
            submitted["arguments"],
            [
                "-a",
                "127.0.0.1",
                "-p",
                "80",
                "--no-banner",
                "--",
                "--script",
                str(self.script_store.root / "demo.nse"),
            ],
        )

    def test_scan_script_selection_persists_across_restart(self) -> None:
        self.script_store.write_script("demo.nse", "print('demo')")
        self.window._create_project()
        self.window._create_scan()
        scan_path = self.store.root / "New Project" / "New Scan"
        self.window._use_script_combo.setCurrentText("Yes")

        self.window.close()
        self.window.deleteLater()
        self.app.processEvents()

        self.window = MainWindow(
            store=self.store,
            config_path=self.config_path,
            script_store=self.script_store,
        )
        self.window._select_path(scan_path)
        self.app.processEvents()

        self.assertEqual(self.window._use_script_combo.currentText(), "Yes")
        self.assertTrue(self.window._scan_script_combo.isEnabled())
        self.assertEqual(self.window._scan_script_combo.currentData(), "demo.nse")

    def test_start_scan_requires_address(self) -> None:
        self.window._create_project()
        self.window._create_scan()
        called = False

        def fake_start(*_args) -> None:
            nonlocal called
            called = True

        self.window._runner.start = fake_start
        self.window._address_edit.clear()

        with patch("ui.main_window.QMessageBox.warning") as warning:
            self.window._start_scan()

        warning.assert_called_once()
        self.assertFalse(called)
        self.assertTrue(self.window._start_button.isEnabled())

    def test_failed_scan_does_not_write_result_file(self) -> None:
        self.window._create_project()
        self.window._create_scan()
        scan_path = self.store.root / "New Project" / "New Scan"
        self.window._runner.start = lambda *_args: None
        self.window._address_edit.setText("127.0.0.1")
        self.window._start_scan()

        with patch("ui.main_window.QMessageBox.critical"):
            self.window._on_scan_finished(1, "", "scan failed")

        self.assertFalse(list(scan_path.glob("result-*.xml")))
        self.assertTrue(self.window._start_button.isEnabled())

    def test_results_tab_loads_xml_file(self) -> None:
        self.window._create_project()
        self.window._create_scan()
        scan_path = self.store.root / "New Project" / "New Scan"
        save_results(
            scan_path,
            [
                PortResult("127.0.0.1", "8080", "tcp", "open", "http-proxy", ""),
                PortResult("127.0.0.1", "80", "tcp", "open", "http", "nginx 1.24"),
            ],
            target="127.0.0.1",
        )

        self.window._tabs.setCurrentIndex(1)
        self.app.processEvents()

        self.assertEqual(self.window._result_table.rowCount(), 2)
        self.assertEqual(
            [self.window._result_table.item(row, 1).text() for row in range(2)],
            ["80", "8080"],
        )
        self.assertEqual(self.window._result_table.item(0, 4).text(), "http")
        self.assertFalse(self.window._result_table.isHidden())
        self.assertIn("result.xml", self.window._result_hint.text())

    def test_results_tab_empty_state(self) -> None:
        self.window._create_project()
        self.window._create_scan()

        self.window._tabs.setCurrentIndex(1)
        self.app.processEvents()

        self.assertEqual(self.window._result_table.rowCount(), 0)
        self.assertTrue(self.window._result_table.isHidden())
        self.assertFalse(self.window._result_file_combo.isEnabled())
        self.assertFalse(self.window._export_csv_button.isEnabled())
        self.assertIn("No scan results", self.window._result_hint.text())

    def test_results_toolbar_exports_current_selection_to_csv(self) -> None:
        self.window._create_project()
        self.window._create_scan()
        scan_path = self.store.root / "New Project" / "New Scan"
        save_results(
            scan_path,
            [PortResult("127.0.0.1", "80", "tcp", "open", "http", "nginx")],
            target="127.0.0.1",
            filename="older.xml",
        )
        save_results(
            scan_path,
            [PortResult("127.0.0.2", "443", "tcp", "open", "https", "nginx 1.24")],
            target="127.0.0.2",
            filename="newer.xml",
        )

        self.window._tabs.setCurrentIndex(1)
        self.app.processEvents()
        selected_index = self.window._result_file_combo.findText("newer.xml")
        self.assertGreaterEqual(selected_index, 0)
        self.window._result_file_combo.setCurrentIndex(selected_index)

        self.assertEqual(self.window._result_controls.count(), 4)
        self.assertEqual(self.window._result_controls.stretch(1), 1)
        self.assertEqual(self.window._export_csv_button.text(), "Export as CSV")
        self.assertEqual(self.window._export_csv_button.objectName(), "SuccessButton")
        self.assertTrue(self.window._export_csv_button.isEnabled())

        csv_path = Path(self._temp.name) / "selected-results"
        with patch(
            "ui.main_window.QFileDialog.getSaveFileName",
            return_value=(str(csv_path), ""),
        ) as dialog:
            self.window._export_current_results_csv()

        dialog.assert_called_once()
        self.assertEqual(dialog.call_args.args[1], "Export scan results as CSV")
        self.assertEqual(
            dialog.call_args.args[2],
            str(scan_path / "newer.csv"),
        )
        self.assertEqual(dialog.call_args.args[3], "CSV files (*.csv)")
        exported = Path(f"{csv_path}.csv")
        self.assertTrue(exported.is_file())
        self.assertEqual(exported.read_bytes()[:3], b"\xef\xbb\xbf")
        with exported.open("r", encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.reader(handle))

        self.assertEqual(
            rows,
            [
                ["Address", "Port", "Protocol", "State", "Service", "Version"],
                ["127.0.0.2", "443", "tcp", "open", "https", "nginx 1.24"],
            ],
        )
        self.assertTrue(
            any(
                "Exported 1 results" in entry[2]
                for entry in self.window._log_entries
            )
        )

    def test_results_tab_caches_documents_until_refreshed(self) -> None:
        self.window._create_project()
        self.window._create_scan()
        scan_path = self.store.root / "New Project" / "New Scan"
        save_results(
            scan_path,
            [PortResult("127.0.0.1", "80", "tcp", "open", "http", "")],
            target="127.0.0.1",
        )

        with patch(
            "ui.main_window.load_result_documents",
            wraps=load_result_documents,
        ) as loader:
            self.window._tabs.setCurrentIndex(1)
            self.app.processEvents()
            self.assertEqual(loader.call_count, 1)

            self.window._tabs.setCurrentIndex(0)
            self.app.processEvents()
            self.window._tabs.setCurrentIndex(1)
            self.app.processEvents()
            self.assertEqual(loader.call_count, 1)

            self.window._reload_results()
            self.app.processEvents()
            self.assertEqual(loader.call_count, 2)

    def test_selecting_project_returns_welcome_page(self) -> None:
        self.window._create_project()
        self.window._create_scan()
        self.assertIs(self.window._stack.currentWidget(), self.window._scan_page)

        self.window._tree.setCurrentItem(self.window._tree.topLevelItem(0))
        self.app.processEvents()

        self.assertIs(self.window._stack.currentWidget(), self.window._welcome_page)

    def test_scan_form_values_survive_switching_scans(self) -> None:
        self.window._create_project()
        self.window._create_scan()
        self.window._create_scan()

        project_item = self.window._tree.topLevelItem(0)
        second_scan = project_item.child(1)
        self.window._tree.setCurrentItem(second_scan)
        self.window._address_edit.setText("10.0.0.0/24")
        self.window._exclude_ip_mode.setCurrentText("Yes")
        self.window._exclude_ip_edit.setText("10.0.0.8,10.0.0.9")
        self.window._ports_edit.setText("80,443")
        self.window._ignore_config_combo.setCurrentText("Yes")
        self.window._udp_mode_combo.setCurrentText("Yes")
        self.window._nmap_version_combo.setCurrentText("Yes")
        self.window._nmap_extra_args_edit.setText("-sC --version-light")
        self.window._exclude_mode.setCurrentText("Yes")
        self.window._exclude_ports_edit.setText("22,3389")

        self.window._tree.setCurrentItem(project_item.child(0))
        self.assertEqual(self.window._exclude_ip_mode.currentText(), "No")
        self.assertFalse(self.window._exclude_ip_edit.isEnabled())
        self.assertEqual(self.window._ignore_config_combo.currentText(), "No")
        self.assertEqual(self.window._udp_mode_combo.currentText(), "No")
        self.assertEqual(self.window._nmap_version_combo.currentText(), "No")
        self.assertEqual(self.window._exclude_mode.currentText(), "No")
        self.assertFalse(self.window._exclude_ports_edit.isEnabled())

        self.window._tree.setCurrentItem(project_item.child(1))
        self.app.processEvents()

        self.assertEqual(self.window._address_edit.text(), "10.0.0.0/24")
        self.assertEqual(self.window._exclude_ip_mode.currentText(), "Yes")
        self.assertEqual(self.window._exclude_ip_edit.text(), "10.0.0.8,10.0.0.9")
        self.assertTrue(self.window._exclude_ip_edit.isEnabled())
        self.assertEqual(self.window._ports_edit.text(), "80,443")
        self.assertEqual(self.window._ignore_config_combo.currentText(), "Yes")
        self.assertEqual(self.window._udp_mode_combo.currentText(), "Yes")
        self.assertEqual(self.window._nmap_version_combo.currentText(), "Yes")
        self.assertEqual(
            self.window._nmap_extra_args_edit.text(),
            "-sC --version-light",
        )
        self.assertTrue(self.window._nmap_extra_args_edit.isEnabled())
        self.assertEqual(self.window._exclude_mode.currentText(), "Yes")
        self.assertEqual(self.window._exclude_ports_edit.text(), "22,3389")
        self.assertTrue(self.window._exclude_ports_edit.isEnabled())

    def test_scan_form_values_persist_across_restart(self) -> None:
        self.window._create_project()
        self.window._create_scan()
        scan_path = self.store.root / "New Project" / "New Scan"
        self.window._address_edit.setText("192.168.1.0/24")
        self.window._address_file_mode.setCurrentText("Yes")
        self.window._address_file_edit.setText("C:/targets.csv")
        self.window._port_mode.setCurrentText("Range")
        self.window._ports_edit.setText("1-2048")
        self.window._exclude_ip_mode.setCurrentText("Yes")
        self.window._exclude_ip_edit.setText("192.168.1.9")
        self.window._exclude_mode.setCurrentText("Yes")
        self.window._exclude_ports_edit.setText("22,3389")
        self.window._ignore_config_combo.setCurrentText("Yes")
        self.window._udp_mode_combo.setCurrentText("Yes")
        self.window._nmap_version_combo.setCurrentText("Yes")
        self.window._nmap_extra_args_edit.setText("-sC --version-light")

        self.window.close()
        self.window.deleteLater()
        self.app.processEvents()
        self.assertTrue((scan_path / "scan_info.xml").is_file())

        self.window = MainWindow(
            store=self.store,
            config_path=self.config_path,
            script_store=self.script_store,
        )
        self.window._select_path(scan_path)
        self.app.processEvents()

        self.assertIs(self.window._stack.currentWidget(), self.window._scan_page)
        self.assertEqual(self.window._address_edit.text(), "192.168.1.0/24")
        self.assertEqual(self.window._address_file_mode.currentText(), "Yes")
        self.assertEqual(
            self.window._address_file_edit.text(),
            "C:/targets.csv",
        )
        self.assertTrue(self.window._address_file_edit.isEnabled())
        self.assertTrue(self.window._address_file_button.isEnabled())
        self.assertEqual(self.window._port_mode.currentText(), "Range")
        self.assertEqual(self.window._ports_edit.text(), "1-2048")
        self.assertEqual(self.window._exclude_ip_mode.currentText(), "Yes")
        self.assertEqual(self.window._exclude_ip_edit.text(), "192.168.1.9")
        self.assertEqual(self.window._exclude_mode.currentText(), "Yes")
        self.assertEqual(self.window._exclude_ports_edit.text(), "22,3389")
        self.assertEqual(self.window._ignore_config_combo.currentText(), "Yes")
        self.assertEqual(self.window._udp_mode_combo.currentText(), "Yes")
        self.assertEqual(self.window._nmap_version_combo.currentText(), "Yes")
        self.assertEqual(
            self.window._nmap_extra_args_edit.text(),
            "-sC --version-light",
        )
        self.assertTrue(self.window._nmap_extra_args_edit.isEnabled())

    def test_sidebar_can_be_closed_and_restored(self) -> None:
        self.window.show()
        self.app.processEvents()
        self.assertTrue(self.window._sidebar.isVisible())

        self.window._view_sidebar_action.setChecked(False)
        self.app.processEvents()
        self.assertFalse(self.window._sidebar.isVisible())

        self.window._view_sidebar_action.setChecked(True)
        self.app.processEvents()
        self.assertTrue(self.window._sidebar.isVisible())


if __name__ == "__main__":
    unittest.main()
