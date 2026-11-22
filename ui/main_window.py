"""主窗口：顶部菜单、可关闭侧栏、项目树与扫描详情页。

左侧栏与 project/ 目录保持同步：
- 文件 -> 新建项目：在 project/ 下创建文件夹，并在侧栏新增顶层项。
- 文件 -> 新建扫描：在选中项目的文件夹下创建子文件夹。
- 右键项目或扫描可重命名，名称同步到本机文件夹。
- 选中扫描后，右侧显示“扫描选项 / 扫描结果”双标签页面。
"""

from __future__ import annotations

import csv
import platform
import re
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from typing import Callable

import PySide6
from PySide6.QtCore import QUrl, Qt
from PySide6.QtGui import (
    QAction,
    QCloseEvent,
    QDesktopServices,
    QGuiApplication,
    QIcon,
    QKeySequence,
    QPainter,
    QPixmap,
)
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QToolButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from config.settings import (
    APP_WINDOW_TITLE,
    APP_VERSION,
    APP_CONFIG_FILE,
    DEFAULT_LANGUAGE,
    DEFAULT_DISPLAY_MODE,
    DEFAULT_NMAP_PATH,
    DEFAULT_WINDOW_MIN_SIZE,
    DEFAULT_WINDOW_SIZE,
    DISPLAY_MODE_DARK,
    DISPLAY_MODE_LIGHT,
    DISPLAY_MODE_SYSTEM,
    GITHUB_ICON_FILE,
    ICONS_DIR,
    LANGUAGE_DIR,
    LOGO_FILE,
    PROJECT_ROOT,
)
from core.command_builder import build_rustscan_args
from core.output_parser import parse_rustscan_output
from core.rustscan_runner import RustscanRunner
from core.scan_planner import (
    ATTACK_PITCHFORK,
    ATTACK_SNIPER,
    ATTACK_TYPES,
    ScanJob,
    build_scan_jobs,
)
from models.project import ProjectNode, ScanNode
from models.result import PortResult
from models.scan_options import ScanOptions
from services.address_file import (
    AddressColumnNotFoundError,
    AddressFileError,
    EmptyAddressFileError,
    UnsupportedAddressFileError,
)
from services.address_port_file import load_address_file
from services.app_config import (
    read_display_mode,
    read_language,
    read_nmap_path,
    write_display_mode,
    write_language,
    write_nmap_path,
)
from services.language_store import LanguageStore
from services.project_store import (
    InvalidNameError,
    NameConflictError,
    ProjectStore,
)
from services.result_store import ResultDocument, load_result_documents, save_results
from services.scan_info_store import load_scan_form, save_scan_form
from services.port_file import (
    EmptyPortFileError,
    PortColumnNotFoundError,
    PortFileError,
    UnsupportedPortFileError,
    load_ports,
)
from services.script_store import (
    InvalidScriptNameError,
    ScriptExistsError,
    ScriptStore,
)
from utils.paths import resolve_rustscan
from utils.theme import apply_app_theme, effective_display_mode

KIND_ROLE = int(Qt.ItemDataRole.UserRole)
PATH_ROLE = KIND_ROLE + 1
KIND_PROJECT = "project"
KIND_SCAN = "scan"

PORT_MODE_PORTS = "ports"
PORT_MODE_RANGE = "range"
PORT_MODE_FILE = "file"
RESULT_COLUMN_KEYS = (
    "results.column_address",
    "results.column_port",
    "results.column_protocol",
    "results.column_state",
    "results.column_service",
    "results.column_version",
)

_ANSI_ESCAPE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")


class MainWindow(QMainWindow):
    """应用主窗口。"""

    def __init__(
        self,
        store: ProjectStore | None = None,
        *,
        language_store: LanguageStore | None = None,
        config_path: Path | str | None = None,
        script_store: ScriptStore | None = None,
    ) -> None:
        super().__init__()
        self._store = store or ProjectStore()
        self._script_store = script_store or ScriptStore()
        self._config_path = Path(config_path) if config_path else APP_CONFIG_FILE
        self._display_mode = read_display_mode(self._config_path)
        self._nmap_path = read_nmap_path(self._config_path)
        if language_store is None:
            self._language_store = LanguageStore(
                LANGUAGE_DIR,
                default_code=DEFAULT_LANGUAGE,
            )
            configured_language = read_language(self._config_path)
            try:
                self._language_store.select(configured_language)
            except KeyError:
                self._language_store.select(DEFAULT_LANGUAGE)
        else:
            self._language_store = language_store
        self._save_language_config()
        self._save_nmap_path_config()
        self._project_icon = QIcon(str(ICONS_DIR / "folder.png"))
        self._scan_icon = QIcon(str(ICONS_DIR / "scan.png"))
        self._current_scan: ScanNode | None = None
        self._form_cache: dict[str, dict[str, object]] = {}
        self._result_documents: list[ResultDocument] = []
        self._result_cache: dict[str, list[ResultDocument]] = {}
        self._log_entries: list[tuple[str, str, str]] = []
        self._scan_output_buffer = ""
        self._active_scan_path: Path | None = None
        self._active_scan_target = ""
        self._active_scan_protocol = "tcp"
        self._scan_jobs: list[ScanJob] = []
        self._scan_job_index = 0
        self._scan_base_options: ScanOptions | None = None
        self._scan_executable: Path | None = None
        self._scan_results: list[PortResult] = []
        self._scan_target_summary = ""
        self._scan_path: Path | None = None

        self._runner = RustscanRunner(self, nmap_path=self._nmap_path)
        self._runner.finished.connect(self._on_scan_finished)
        self._runner.failedToStart.connect(self._on_scan_failed_to_start)
        self._runner.outputReceived.connect(self._on_scan_output_received)
        self._apply_theme()
        self._connect_system_theme()

        self.setWindowTitle(APP_WINDOW_TITLE)
        self.resize(*DEFAULT_WINDOW_SIZE)
        self.setMinimumSize(*DEFAULT_WINDOW_MIN_SIZE)

        self._build_ui()
        self._build_menus()
        self._reload_tree()
        self._show_welcome_page()
        self.statusBar().showMessage(self._t("status.ready"))
        self._append_log(
            "INFO",
            self._t("log.application_started", version=APP_VERSION),
        )

    def _t(self, key: str, **values: object) -> str:
        return self._language_store.text(key, **values)

    def _set_status(
        self,
        message: str,
        timeout: int = 0,
        *,
        level: str = "INFO",
    ) -> None:
        self.statusBar().showMessage(message, timeout)
        self._append_log(level, message)

    def _append_log(self, level: str, message: str) -> None:
        clean = _ANSI_ESCAPE.sub("", message).strip()
        if not clean:
            return
        timestamp = datetime.now().strftime("%H:%M:%S")
        for line in clean.splitlines():
            if not line.strip():
                continue
            entry = (timestamp, level.upper(), line.rstrip())
            self._log_entries.append(entry)
            self._append_log_entry(entry)
        if len(self._log_entries) > 5000:
            del self._log_entries[: len(self._log_entries) - 5000]

    def _append_log_entry(self, entry: tuple[str, str, str]) -> None:
        if not hasattr(self, "_log_view"):
            return
        timestamp, level, message = entry
        scrollbar = self._log_view.verticalScrollBar()
        follow_tail = scrollbar.value() >= scrollbar.maximum() - 4
        self._log_view.appendPlainText(f"{timestamp}  {level:<5}  {message}")
        if follow_tail:
            scrollbar.setValue(scrollbar.maximum())

    def _on_scan_output_received(self, chunk: str) -> None:
        if not chunk:
            return
        self._scan_output_buffer += chunk
        while True:
            positions = [
                index
                for index in (
                    self._scan_output_buffer.find("\n"),
                    self._scan_output_buffer.find("\r"),
                )
                if index >= 0
            ]
            if not positions:
                break
            index = min(positions)
            line = self._scan_output_buffer[:index]
            self._scan_output_buffer = self._scan_output_buffer[index + 1 :]
            if line.strip():
                self._append_log("SCAN", line)

    def _flush_scan_output(self) -> None:
        if self._scan_output_buffer.strip():
            self._append_log("SCAN", self._scan_output_buffer)
        self._scan_output_buffer = ""

    def _save_language_config(self) -> OSError | None:
        try:
            write_language(self._config_path, self._language_store.current_code)
        except OSError as exc:
            return exc
        return None

    def _apply_theme(self) -> str:
        app = QApplication.instance()
        if app is None:
            return effective_display_mode(self._display_mode)
        return apply_app_theme(app, self._display_mode)

    def _save_display_mode_config(self) -> OSError | None:
        try:
            write_display_mode(self._config_path, self._display_mode)
        except OSError as exc:
            return exc
        return None

    def _save_nmap_path_config(self) -> OSError | None:
        try:
            write_nmap_path(self._config_path, self._nmap_path)
        except OSError as exc:
            return exc
        return None

    def _connect_system_theme(self) -> None:
        scheme_changed = getattr(
            QGuiApplication.styleHints(),
            "colorSchemeChanged",
            None,
        )
        if scheme_changed is not None:
            scheme_changed.connect(self._on_system_color_scheme_changed)

    def _on_system_color_scheme_changed(self, *_: object) -> None:
        if self._display_mode == DISPLAY_MODE_SYSTEM:
            self._apply_theme()

    def _build_ui(self) -> None:
        root = QWidget()
        root.setObjectName("RootPanel")
        layout = QHBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self._sidebar = self._build_sidebar()
        layout.addWidget(self._sidebar)
        layout.addWidget(self._build_content(), 1)
        self.setCentralWidget(root)

    def _build_menus(self) -> None:
        menu_bar = self.menuBar()
        menu_bar.setNativeMenuBar(False)

        file_menu = menu_bar.addMenu(self._t("menu.file"))
        self._add_action(
            file_menu,
            self._t("menu.new_project"),
            "Ctrl+Shift+N",
            self._create_project,
        )
        self._add_action(
            file_menu,
            self._t("menu.new_scan"),
            "Ctrl+N",
            self._create_scan,
        )
        file_menu.addSeparator()
        self._add_action(file_menu, self._t("menu.exit"), "Ctrl+Q", self.close)

        edit_menu = menu_bar.addMenu(self._t("menu.edit"))
        self._add_action(
            edit_menu,
            self._t("menu.rename_selected"),
            "F2",
            self._rename_selected,
        )
        self._add_action(
            edit_menu,
            self._t("menu.refresh_projects"),
            "F5",
            self._reload_tree,
        )
        edit_menu.addSeparator()
        self._settings_action = self._add_action(
            edit_menu,
            self._t("menu.settings"),
            "Ctrl+,",
            self._show_settings_page,
        )
        self._main_interface_action = self._add_action(
            edit_menu,
            self._t("menu.main_interface"),
            "Ctrl+1",
            self._show_main_interface,
        )

        view_menu = menu_bar.addMenu(self._t("menu.view"))
        self._view_sidebar_action = QAction(self._t("menu.show_sidebar"), self)
        self._view_sidebar_action.setCheckable(True)
        self._view_sidebar_action.setChecked(True)
        self._view_sidebar_action.setShortcut(QKeySequence("Ctrl+B"))
        self._view_sidebar_action.toggled.connect(self._set_sidebar_visible)
        view_menu.addAction(self._view_sidebar_action)

        scripts_menu = menu_bar.addMenu(self._t("menu.scripts"))
        self._add_action(
            scripts_menu,
            self._t("menu.manage_scripts"),
            None,
            self._show_scripts_page,
        )
        self._add_action(
            scripts_menu,
            self._t("menu.add_script"),
            None,
            self._show_add_script_dialog,
        )

        help_menu = menu_bar.addMenu(self._t("menu.help"))
        self._add_action(
            help_menu,
            self._t("menu.about"),
            None,
            self._show_about,
        )

    @staticmethod
    def _add_action(
        menu: QMenu,
        text: str,
        shortcut: str | None,
        slot: Callable[[], None],
    ) -> QAction:
        action = QAction(text, menu)
        if shortcut:
            action.setShortcut(QKeySequence(shortcut))
        action.triggered.connect(lambda _checked=False, fn=slot: fn())
        menu.addAction(action)
        return action

    def _build_sidebar(self) -> QFrame:
        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(260)

        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(14, 16, 14, 14)
        layout.setSpacing(10)

        header = QHBoxLayout()
        header.setContentsMargins(6, 0, 0, 0)
        header.setSpacing(6)

        brand = QVBoxLayout()
        brand.setSpacing(0)
        logo = QLabel()
        logo.setObjectName("BrandLogo")
        logo.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        logo_pixmap = QPixmap(str(LOGO_FILE))
        if logo_pixmap.isNull():
            logo.setText("RustScan")
            logo.setObjectName("BrandTitle")
        else:
            logo_pixmap = logo_pixmap.scaledToWidth(
                128,
                Qt.TransformationMode.SmoothTransformation,
            )
            logo.setPixmap(logo_pixmap)
            logo.setFixedSize(logo_pixmap.size())
        subtitle = QLabel(self._t("sidebar.subtitle"))
        subtitle.setObjectName("BrandSubtitle")
        brand.addWidget(logo)
        brand.addWidget(subtitle)
        header.addLayout(brand, 1)

        close_button = QToolButton()
        close_button.setObjectName("SidebarCloseButton")
        close_button.setText("×")
        close_button.setToolTip(self._t("sidebar.close_tooltip"))
        close_button.setFixedSize(24, 24)
        close_button.clicked.connect(self._hide_sidebar)
        header.addWidget(close_button, 0, Qt.AlignmentFlag.AlignTop)
        layout.addLayout(header)

        section = QLabel(self._t("sidebar.section_projects"))
        section.setObjectName("SectionLabel")
        layout.addWidget(section)

        self._tree = QTreeWidget()
        self._tree.setObjectName("ProjectTree")
        self._tree.setHeaderHidden(True)
        self._tree.setColumnCount(1)
        self._tree.setIndentation(14)
        self._tree.setUniformRowHeights(True)
        self._tree.setAnimated(True)
        self._tree.setTextElideMode(Qt.TextElideMode.ElideRight)
        self._tree.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._tree.customContextMenuRequested.connect(self._show_context_menu)
        self._tree.itemSelectionChanged.connect(self._on_selection_changed)
        self._tree.itemClicked.connect(self._on_tree_item_clicked)
        layout.addWidget(self._tree, 1)

        version = QLabel(f"v{APP_VERSION}")
        version.setObjectName("Muted")
        layout.addWidget(version)
        return sidebar

    def _build_content(self) -> QWidget:
        content = QWidget()
        content.setObjectName("ContentPanel")
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._stack = QStackedWidget()
        self._stack.setObjectName("ContentStack")
        self._welcome_page = self._build_welcome_page()
        self._scan_page = self._build_scan_page()
        self._settings_page = self._build_settings_page()
        self._scripts_page = self._build_scripts_page()
        self._stack.addWidget(self._welcome_page)
        self._stack.addWidget(self._scan_page)
        self._stack.addWidget(self._settings_page)
        self._stack.addWidget(self._scripts_page)
        layout.addWidget(self._stack)
        return content

    def _build_welcome_page(self) -> QWidget:
        page = QWidget()
        page.setObjectName("WelcomePage")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(32, 28, 32, 28)
        layout.setSpacing(16)

        heading = QLabel(self._t("welcome.title"))
        heading.setObjectName("PageTitle")
        description = QLabel(self._t("welcome.description"))
        description.setObjectName("Muted")
        description.setWordWrap(True)

        layout.addWidget(heading)
        layout.addWidget(description)
        layout.addWidget(self._build_status_card())
        layout.addStretch(1)
        return page

    def _build_scan_page(self) -> QWidget:
        page = QWidget()
        page.setObjectName("ScanPage")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(32, 26, 32, 24)
        layout.setSpacing(10)

        self._scan_title = QLabel(self._t("scan.title"))
        self._scan_title.setObjectName("PageTitle")
        self._scan_path_label = QLabel()
        self._scan_path_label.setObjectName("Muted")
        self._scan_path_label.setWordWrap(True)
        self._scan_path_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        layout.addWidget(self._scan_title)
        layout.addWidget(self._scan_path_label)

        self._tabs = QTabWidget()
        self._tabs.setObjectName("ScanTabs")
        self._tabs.addTab(self._build_scan_options_tab(), self._t("scan.tab_options"))
        self._tabs.addTab(self._build_scan_results_tab(), self._t("scan.tab_results"))
        self._tabs.addTab(self._build_logs_tab(), self._t("scan.tab_logs"))
        self._tabs.currentChanged.connect(self._on_tab_changed)
        layout.addWidget(self._tabs, 1)
        return page

    def _build_settings_page(self) -> QWidget:
        page = QWidget()
        page.setObjectName("SettingsPage")
        layout = QHBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        settings_sidebar = QFrame()
        settings_sidebar.setObjectName("SettingsSidebar")
        settings_sidebar.setFixedWidth(220)
        side_layout = QVBoxLayout(settings_sidebar)
        side_layout.setContentsMargins(14, 24, 14, 18)
        side_layout.setSpacing(8)

        nav_title = QLabel(self._t("settings.title"))
        nav_title.setObjectName("SettingsNavTitle")
        side_layout.addWidget(nav_title)
        side_layout.addSpacing(12)

        self._settings_nav_group = QButtonGroup(page)
        self._settings_nav_group.setExclusive(True)
        language_nav = self._build_settings_nav_button(
            self._t("settings.nav_language")
        )
        interface_nav = self._build_settings_nav_button(
            self._t("settings.nav_interface")
        )
        nmap_nav = self._build_settings_nav_button(
            self._t("settings.nav_nmap")
        )
        self._settings_nav_group.addButton(language_nav, 0)
        self._settings_nav_group.addButton(interface_nav, 1)
        self._settings_nav_group.addButton(nmap_nav, 2)
        language_nav.setChecked(True)
        side_layout.addWidget(language_nav)
        side_layout.addWidget(interface_nav)
        side_layout.addWidget(nmap_nav)
        side_layout.addStretch(1)

        content = QWidget()
        content.setObjectName("SettingsContent")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(32, 28, 32, 28)
        content_layout.setSpacing(14)

        heading = QLabel(self._t("settings.title"))
        heading.setObjectName("PageTitle")
        subtitle = QLabel(self._t("settings.subtitle"))
        subtitle.setObjectName("Muted")
        subtitle.setWordWrap(True)
        content_layout.addWidget(heading)
        content_layout.addWidget(subtitle)

        self._settings_stack = QStackedWidget()
        self._settings_stack.setObjectName("SettingsSectionStack")
        self._settings_stack.addWidget(self._build_language_settings_section())
        self._settings_stack.addWidget(self._build_interface_settings_section())
        self._settings_stack.addWidget(self._build_nmap_settings_section())
        self._settings_nav_group.idClicked.connect(self._show_settings_section)
        content_layout.addWidget(self._settings_stack, 1)

        layout.addWidget(settings_sidebar)
        layout.addWidget(content, 1)
        return page

    def _build_settings_nav_button(self, text: str) -> QPushButton:
        button = QPushButton(text)
        button.setObjectName("SettingsNavButton")
        button.setCheckable(True)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        return button

    def _build_language_settings_section(self) -> QWidget:
        section = QWidget()
        section.setObjectName("SettingsSectionPage")
        section_layout = QVBoxLayout(section)
        section_layout.setContentsMargins(0, 0, 0, 0)
        section_layout.setSpacing(0)

        card = QFrame()
        card.setObjectName("Card")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(22, 20, 22, 20)
        card_layout.setSpacing(10)

        language_title = QLabel(self._t("settings.language_title"))
        language_title.setObjectName("CardTitle")
        language_description = QLabel(self._t("settings.language_description"))
        language_description.setObjectName("Muted")
        language_description.setWordWrap(True)
        card_layout.addWidget(language_title)
        card_layout.addWidget(language_description)

        language_row = QHBoxLayout()
        language_row.setSpacing(16)
        language_label = QLabel(self._t("settings.language_label"))
        language_label.setObjectName("FieldLabel")
        self._language_combo = QComboBox()
        self._language_combo.setMinimumWidth(220)
        for language in self._language_store.languages():
            self._language_combo.addItem(language.name, language.code)
        current_index = self._language_combo.findData(self._language_store.current_code)
        if current_index >= 0:
            self._language_combo.setCurrentIndex(current_index)
        self._language_combo.currentIndexChanged.connect(
            self._on_language_combo_changed
        )
        language_row.addWidget(language_label)
        language_row.addWidget(self._language_combo, 1)
        card_layout.addLayout(language_row)

        language_hint = QLabel(self._t("settings.language_hint"))
        language_hint.setObjectName("Muted")
        language_hint.setWordWrap(True)
        card_layout.addWidget(language_hint)

        section_layout.addWidget(card)
        section_layout.addStretch(1)
        return section

    def _build_interface_settings_section(self) -> QWidget:
        section = QWidget()
        section.setObjectName("SettingsSectionPage")
        section_layout = QVBoxLayout(section)
        section_layout.setContentsMargins(0, 0, 0, 0)
        section_layout.setSpacing(0)

        card = QFrame()
        card.setObjectName("Card")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(22, 20, 22, 20)
        card_layout.setSpacing(10)

        title = QLabel(self._t("settings.interface_title"))
        title.setObjectName("CardTitle")
        description = QLabel(self._t("settings.interface_description"))
        description.setObjectName("Muted")
        description.setWordWrap(True)
        card_layout.addWidget(title)
        card_layout.addWidget(description)

        display_row = QHBoxLayout()
        display_row.setSpacing(16)
        display_label = QLabel(self._t("settings.display_mode_label"))
        display_label.setObjectName("FieldLabel")
        self._display_mode_combo = QComboBox()
        self._display_mode_combo.setMinimumWidth(220)
        self._display_mode_combo.addItem(
            self._t("settings.display_mode_day"),
            DISPLAY_MODE_LIGHT,
        )
        self._display_mode_combo.addItem(
            self._t("settings.display_mode_night"),
            DISPLAY_MODE_DARK,
        )
        self._display_mode_combo.addItem(
            self._t("settings.display_mode_system"),
            DISPLAY_MODE_SYSTEM,
        )
        current_index = self._display_mode_combo.findData(self._display_mode)
        if current_index >= 0:
            self._display_mode_combo.setCurrentIndex(current_index)
        self._display_mode_combo.currentIndexChanged.connect(
            self._on_display_mode_combo_changed
        )
        display_row.addWidget(display_label)
        display_row.addWidget(self._display_mode_combo, 1)
        card_layout.addLayout(display_row)

        hint = QLabel(self._t("settings.display_mode_hint"))
        hint.setObjectName("Muted")
        hint.setWordWrap(True)
        card_layout.addWidget(hint)

        section_layout.addWidget(card)
        section_layout.addStretch(1)
        return section

    def _build_nmap_settings_section(self) -> QWidget:
        section = QWidget()
        section.setObjectName("SettingsSectionPage")
        section_layout = QVBoxLayout(section)
        section_layout.setContentsMargins(0, 0, 0, 0)
        section_layout.setSpacing(0)

        card = QFrame()
        card.setObjectName("Card")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(22, 20, 22, 20)
        card_layout.setSpacing(10)

        title = QLabel(self._t("settings.nmap_title"))
        title.setObjectName("CardTitle")
        description = QLabel(self._t("settings.nmap_description"))
        description.setObjectName("Muted")
        description.setWordWrap(True)
        card_layout.addWidget(title)
        card_layout.addWidget(description)

        path_label = QLabel(self._t("settings.nmap_path_label"))
        path_label.setObjectName("FieldLabel")
        self._nmap_path_edit = QLineEdit(self._nmap_path)
        self._nmap_path_edit.setObjectName("NmapPathEdit")
        self._nmap_path_edit.setPlaceholderText(
            self._t("settings.nmap_path_placeholder")
        )
        self._nmap_path_edit.setClearButtonEnabled(True)
        self._nmap_path_edit.editingFinished.connect(self._on_nmap_path_changed)
        card_layout.addWidget(path_label)
        card_layout.addWidget(self._nmap_path_edit)

        hint = QLabel(self._t("settings.nmap_path_hint"))
        hint.setObjectName("Muted")
        hint.setWordWrap(True)
        card_layout.addWidget(hint)

        section_layout.addWidget(card)
        section_layout.addStretch(1)
        return section

    def _show_settings_section(self, index: int) -> None:
        if not 0 <= index < self._settings_stack.count():
            return
        self._settings_stack.setCurrentIndex(index)
        button = self._settings_nav_group.button(index)
        if button is not None:
            button.setChecked(True)

    def _build_scripts_page(self) -> QWidget:
        page = QWidget()
        page.setObjectName("ScriptsPage")
        layout = QHBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        scripts_sidebar = QFrame()
        scripts_sidebar.setObjectName("ScriptsSidebar")
        scripts_sidebar.setFixedWidth(240)
        side_layout = QVBoxLayout(scripts_sidebar)
        side_layout.setContentsMargins(14, 24, 14, 18)
        side_layout.setSpacing(10)

        nav_title = QLabel(self._t("scripts.manage_title"))
        nav_title.setObjectName("SettingsNavTitle")
        side_layout.addWidget(nav_title)

        description = QLabel(self._t("scripts.description"))
        description.setObjectName("Muted")
        description.setWordWrap(True)
        side_layout.addWidget(description)
        side_layout.addSpacing(4)

        self._script_list = QListWidget()
        self._script_list.setObjectName("ScriptList")
        self._script_list.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self._script_list.setTextElideMode(Qt.TextElideMode.ElideRight)
        self._script_list.setContextMenuPolicy(
            Qt.ContextMenuPolicy.CustomContextMenu
        )
        self._script_list.customContextMenuRequested.connect(
            self._show_script_context_menu
        )
        self._script_list.currentItemChanged.connect(self._on_script_selected)
        side_layout.addWidget(self._script_list, 1)

        content = QWidget()
        content.setObjectName("ScriptsContent")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(32, 28, 32, 28)
        content_layout.setSpacing(10)

        heading = QLabel(self._t("scripts.manage_title"))
        heading.setObjectName("PageTitle")
        self._script_title = QLabel(self._t("scripts.select_hint"))
        self._script_title.setObjectName("Muted")
        self._script_content = QPlainTextEdit()
        self._script_content.setObjectName("ScriptContent")
        self._script_content.setReadOnly(True)
        self._script_content.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self._script_content.setPlaceholderText(self._t("scripts.select_hint"))

        content_layout.addWidget(heading)
        content_layout.addWidget(self._script_title)
        content_layout.addWidget(self._script_content, 1)

        layout.addWidget(scripts_sidebar)
        layout.addWidget(content, 1)

        self._refresh_script_list()
        return page

    def _show_scripts_page(self) -> None:
        if self._stack.currentWidget() is not self._scripts_page:
            self._remember_scan_form()
        self._refresh_script_list()
        self._stack.setCurrentWidget(self._scripts_page)
        self._view_sidebar_action.setChecked(False)

    def _refresh_script_list(self, select: str | None = None) -> None:
        if not hasattr(self, "_script_list"):
            return
        if select is None:
            current = self._script_list.currentItem()
            select = current.text() if current is not None else ""

        names = self._script_store.list_scripts()
        self._script_list.blockSignals(True)
        self._script_list.clear()
        for name in names:
            self._script_list.addItem(QListWidgetItem(name))
        self._script_list.blockSignals(False)

        if not names:
            self._show_script_placeholder()
            return

        target_row = next(
            (index for index, name in enumerate(names) if name == select),
            0,
        )
        self._script_list.setCurrentRow(target_row)

    def _on_script_selected(
        self,
        current: QListWidgetItem | None,
        _previous: QListWidgetItem | None = None,
    ) -> None:
        if current is None:
            self._show_script_placeholder()
            return
        name = current.text()
        self._script_title.setText(name)
        try:
            content = self._script_store.read_script(name)
        except OSError as exc:
            self._script_content.setPlainText(
                self._t("scripts.read_failed", error=exc)
            )
            return
        self._script_content.setPlainText(content)

    def _show_script_placeholder(self) -> None:
        self._script_title.setText(self._t("scripts.select_hint"))
        self._script_content.clear()
        self._script_content.setPlaceholderText(self._t("scripts.empty"))

    def _show_script_context_menu(self, position) -> None:
        item = self._script_list.itemAt(position)
        if item is None:
            return
        self._script_list.setCurrentItem(item)
        menu = self._build_script_context_menu(item)
        menu.exec(self._script_list.viewport().mapToGlobal(position))

    def _build_script_context_menu(self, item: QListWidgetItem) -> QMenu:
        menu = QMenu(self)
        open_action = menu.addAction(self._t("context.open_explorer"))
        open_action.triggered.connect(
            lambda _checked=False, name=item.text(): self._open_script_in_explorer(
                name
            )
        )
        menu.addSeparator()
        delete_action = menu.addAction(self._t("context.delete_script"))
        delete_action.triggered.connect(
            lambda _checked=False, name=item.text(): self._delete_script(name)
        )
        return menu

    def _open_script_in_explorer(self, name: str) -> None:
        try:
            self._script_store.ensure()
        except OSError as exc:
            QMessageBox.critical(
                self,
                self._t("dialog.open_failed"),
                self._t("dialog.cannot_access_folder", error=exc),
            )
            return
        folder = self._script_store.root
        if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder))):
            QMessageBox.warning(
                self,
                self._t("dialog.open_failed"),
                self._t("dialog.cannot_open_folder", path=folder),
            )

    def _delete_script(self, name: str) -> None:
        answer = QMessageBox.question(
            self,
            self._t("context.delete_script"),
            self._t("dialog.delete_script_body", name=name),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        try:
            self._script_store.delete_script(name)
        except (OSError, InvalidScriptNameError) as exc:
            QMessageBox.critical(
                self,
                self._t("dialog.delete_failed"),
                self._t("dialog.cannot_delete_script", error=exc),
            )
            return

        self._refresh_script_list()
        self._refresh_scan_script_combo()
        self._set_status(self._t("status.script_deleted", name=name), 5000)

    def _build_add_script_dialog(
        self,
    ) -> tuple[QDialog, QLineEdit, QPlainTextEdit, QPushButton]:
        dialog = QDialog(self)
        dialog.setObjectName("AddScriptDialog")
        dialog.setWindowTitle(self._t("dialog.add_script_title"))
        dialog.setModal(True)
        dialog.setMinimumSize(560, 480)

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(24, 20, 24, 18)
        layout.setSpacing(12)

        heading = QLabel(self._t("dialog.add_script_title"))
        heading.setObjectName("CardTitle")
        layout.addWidget(heading)

        name_label = QLabel(self._t("dialog.script_name"))
        name_label.setObjectName("FieldLabel")
        name_edit = QLineEdit()
        name_edit.setPlaceholderText(self._t("dialog.script_name_placeholder"))
        layout.addWidget(name_label)
        layout.addWidget(name_edit)

        content_label = QLabel(self._t("dialog.script_content"))
        content_label.setObjectName("FieldLabel")
        content_edit = QPlainTextEdit()
        content_edit.setObjectName("ScriptEditor")
        content_edit.setPlaceholderText(self._t("dialog.script_content_placeholder"))
        content_edit.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        layout.addWidget(content_label)
        layout.addWidget(content_edit, 1)

        actions = QHBoxLayout()
        actions.setSpacing(8)
        actions.addStretch(1)
        cancel = QPushButton(self._t("dialog.cancel"))
        cancel.setObjectName("DialogCancelButton")
        cancel.clicked.connect(dialog.reject)
        confirm = QPushButton(self._t("dialog.confirm"))
        confirm.setObjectName("SuccessButton")
        confirm.setDefault(True)
        confirm.setEnabled(False)
        name_edit.textChanged.connect(
            lambda text: confirm.setEnabled(bool(text.strip()))
        )
        actions.addWidget(cancel)
        actions.addWidget(confirm)
        layout.addLayout(actions)
        return dialog, name_edit, content_edit, confirm

    def _show_add_script_dialog(self) -> None:
        dialog, name_edit, content_edit, confirm = self._build_add_script_dialog()

        def submit() -> None:
            try:
                name = self._script_store.write_script(
                    name_edit.text(),
                    content_edit.toPlainText(),
                )
            except InvalidScriptNameError:
                QMessageBox.warning(
                    dialog,
                    self._t("dialog.invalid_name"),
                    self._t("dialog.invalid_name_message"),
                )
                name_edit.setFocus()
                return
            except ScriptExistsError:
                QMessageBox.warning(
                    dialog,
                    self._t("dialog.add_script_failed"),
                    self._t("dialog.script_name_exists"),
                )
                name_edit.setFocus()
                return
            except OSError as exc:
                QMessageBox.critical(
                    dialog,
                    self._t("dialog.add_script_failed"),
                    self._t("dialog.cannot_write_script", error=exc),
                )
                return
            dialog.accept()
            self._refresh_script_list(select=name)
            self._set_status(self._t("status.script_added", name=name), 5000)

        confirm.clicked.connect(submit)
        dialog.exec()

    def _build_scan_options_tab(self) -> QWidget:
        page = QWidget()
        page.setObjectName("ScanOptionsPage")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 22, 24, 22)
        layout.setSpacing(16)

        self._scan_options_scroll = QScrollArea()
        self._scan_options_scroll.setObjectName("ScanOptionsScroll")
        self._scan_options_scroll.setWidgetResizable(True)
        self._scan_options_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scan_options_scroll.viewport().setAutoFillBackground(False)
        self._scan_options_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self._scan_options_scroll.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )

        content = QWidget()
        content.setObjectName("ScanOptionsContent")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        card = QFrame()
        card.setObjectName("Card")
        form = QVBoxLayout(card)
        form.setContentsMargins(20, 18, 20, 18)
        form.setSpacing(8)

        form.addLayout(
            self._build_label_row(self._t("scan.address_label"), required=True)
        )
        self._address_edit = QLineEdit()
        self._address_edit.setPlaceholderText(self._t("scan.address_placeholder"))
        form.addWidget(self._address_edit)

        form.addSpacing(8)
        self._address_file_mode = self._build_yes_no_combo()
        form.addLayout(
            self._build_combo_row(
                self._t("scan.import_address_label"),
                self._address_file_mode,
            )
        )
        address_file_row = QHBoxLayout()
        address_file_row.setSpacing(10)
        self._address_file_edit = QLineEdit()
        self._address_file_edit.setPlaceholderText(
            self._t("scan.import_address_placeholder")
        )
        self._address_file_edit.setEnabled(False)
        self._address_file_button = QPushButton(self._t("scan.choose_file"))
        self._address_file_button.setMinimumWidth(90)
        self._address_file_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._address_file_button.setEnabled(False)
        self._address_file_mode.currentIndexChanged.connect(
            self._on_address_file_mode_changed
        )
        self._address_file_button.clicked.connect(self._choose_address_file)
        address_file_row.addWidget(self._address_file_edit, 1)
        address_file_row.addWidget(self._address_file_button)
        form.addLayout(address_file_row)

        form.addSpacing(8)
        form.addLayout(self._build_label_row(self._t("scan.exclude_ip_label")))
        exclude_ip_row = QHBoxLayout()
        exclude_ip_row.setSpacing(10)
        self._exclude_ip_mode = self._build_yes_no_combo()
        self._exclude_ip_edit = QLineEdit()
        self._exclude_ip_edit.setPlaceholderText(
            self._t("scan.exclude_ip_placeholder")
        )
        self._exclude_ip_edit.setEnabled(False)
        self._exclude_ip_mode.currentIndexChanged.connect(
            self._on_exclude_ip_mode_changed
        )
        exclude_ip_row.addWidget(self._exclude_ip_mode)
        exclude_ip_row.addWidget(self._exclude_ip_edit, 1)
        form.addLayout(exclude_ip_row)

        form.addSpacing(10)
        form.addLayout(self._build_label_row(self._t("scan.ports_title")))
        mode_row = QHBoxLayout()
        mode_row.setSpacing(10)
        self._port_mode = QComboBox()
        self._port_mode.addItem(self._t("scan.port_mode_ports"), PORT_MODE_PORTS)
        self._port_mode.addItem(self._t("scan.port_mode_range"), PORT_MODE_RANGE)
        self._port_mode.addItem(self._t("scan.port_mode_file"), PORT_MODE_FILE)
        self._port_mode.setFixedWidth(130)
        self._ports_edit = QLineEdit()
        self._ports_edit.setPlaceholderText(self._t("scan.ports_placeholder_ports"))
        self._ports_file_button = QPushButton(self._t("scan.choose_file"))
        self._ports_file_button.setMinimumWidth(90)
        self._ports_file_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._ports_file_button.setEnabled(False)
        self._port_mode.currentIndexChanged.connect(self._on_port_mode_changed)
        self._ports_file_button.clicked.connect(self._choose_port_file)
        mode_row.addWidget(self._port_mode)
        mode_row.addWidget(self._ports_edit, 1)
        mode_row.addWidget(self._ports_file_button)
        form.addLayout(mode_row)

        self._attack_type_widget = QWidget()
        attack_row = QHBoxLayout(self._attack_type_widget)
        attack_row.setContentsMargins(0, 0, 0, 0)
        attack_row.setSpacing(10)
        attack_label = QLabel(self._t("scan.attack_type_label"))
        attack_label.setObjectName("FieldLabel")
        self._attack_type_combo = QComboBox()
        self._attack_type_combo.addItem(
            self._t("scan.attack_sniper"),
            ATTACK_SNIPER,
        )
        self._attack_type_combo.addItem(
            self._t("scan.attack_pitchfork"),
            ATTACK_PITCHFORK,
        )
        attack_row.addWidget(attack_label)
        attack_row.addStretch(1)
        attack_row.addWidget(self._attack_type_combo)
        self._attack_type_widget.setVisible(False)
        form.addWidget(self._attack_type_widget)

        form.addSpacing(8)
        form.addLayout(self._build_label_row(self._t("scan.exclude_ports_label")))
        exclude_row = QHBoxLayout()
        exclude_row.setSpacing(10)
        self._exclude_mode = self._build_yes_no_combo()
        self._exclude_ports_edit = QLineEdit()
        self._exclude_ports_edit.setPlaceholderText(
            self._t("scan.exclude_ports_placeholder")
        )
        self._exclude_ports_edit.setEnabled(False)
        self._exclude_mode.currentIndexChanged.connect(self._on_exclude_mode_changed)
        exclude_row.addWidget(self._exclude_mode)
        exclude_row.addWidget(self._exclude_ports_edit, 1)
        form.addLayout(exclude_row)

        form.addSpacing(6)
        self._ignore_config_combo = self._build_yes_no_combo()
        form.addLayout(
            self._build_combo_row(
                self._t("scan.ignore_config_label"),
                self._ignore_config_combo,
            )
        )
        self._udp_mode_combo = self._build_yes_no_combo()
        form.addLayout(self._build_combo_row(self._t("scan.udp_label"), self._udp_mode_combo))
        self._nmap_version_combo = self._build_yes_no_combo()
        form.addLayout(
            self._build_combo_row(
                self._t("scan.nmap_version_label"),
                self._nmap_version_combo,
            )
        )
        self._nmap_extra_args_edit = QLineEdit()
        self._nmap_extra_args_edit.setPlaceholderText(
            self._t("scan.nmap_extra_args_placeholder")
        )
        self._nmap_extra_args_edit.setEnabled(False)
        self._nmap_version_combo.currentIndexChanged.connect(
            self._on_nmap_version_mode_changed
        )
        form.addWidget(self._nmap_extra_args_edit)

        form.addSpacing(6)
        self._use_script_combo = self._build_yes_no_combo()
        form.addLayout(
            self._build_combo_row(
                self._t("scan.use_script_label"),
                self._use_script_combo,
            )
        )
        self._scan_script_combo = QComboBox()
        self._scan_script_combo.setObjectName("ScanScriptCombo")
        self._refresh_scan_script_combo()
        self._scan_script_combo.setEnabled(False)
        self._use_script_combo.currentIndexChanged.connect(
            self._on_use_script_mode_changed
        )
        form.addWidget(self._scan_script_combo)

        tip = QLabel(self._t("scan.tip"))
        tip.setObjectName("Muted")
        tip.setWordWrap(True)
        form.addSpacing(8)
        form.addWidget(tip)

        content_layout.addWidget(card)
        content_layout.addStretch(1)
        self._scan_options_scroll.setWidget(content)
        layout.addWidget(self._scan_options_scroll, 1)

        action_row = QHBoxLayout()
        action_row.setContentsMargins(0, 0, 0, 0)
        action_row.addStretch(1)
        self._start_button = QPushButton(self._t("scan.start"))
        self._start_button.setObjectName("StartScanButton")
        self._start_button.setMinimumWidth(150)
        self._start_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._start_button.clicked.connect(self._start_scan)
        if self._runner.is_running:
            self._start_button.setEnabled(False)
        action_row.addWidget(self._start_button)
        layout.addLayout(action_row)
        return page

    def _build_scan_results_tab(self) -> QWidget:
        page = QWidget()
        page.setObjectName("ScanResultsPage")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 22, 24, 22)
        layout.setSpacing(10)

        controls = QHBoxLayout()
        controls.setSpacing(10)
        label = QLabel(self._t("results.file_label"))
        label.setObjectName("FieldLabel")
        self._result_file_combo = QComboBox()
        self._result_file_combo.setMinimumWidth(220)
        self._result_file_combo.currentIndexChanged.connect(self._on_result_file_changed)
        self._refresh_results_button = QPushButton(self._t("results.refresh"))
        self._refresh_results_button.clicked.connect(self._reload_results)
        self._export_csv_button = QPushButton(self._t("results.export_csv"))
        self._export_csv_button.setObjectName("SuccessButton")
        self._export_csv_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._export_csv_button.clicked.connect(self._export_current_results_csv)
        controls.addWidget(label)
        controls.addWidget(self._result_file_combo, 1)
        controls.addWidget(self._refresh_results_button)
        controls.addWidget(self._export_csv_button)
        self._result_controls = controls
        layout.addLayout(controls)

        self._result_hint = QLabel()
        self._result_hint.setObjectName("Muted")
        self._result_hint.setWordWrap(True)
        layout.addWidget(self._result_hint)

        self._result_table = QTableWidget(0, len(RESULT_COLUMN_KEYS))
        self._result_table.setObjectName("ResultTable")
        self._result_table.setHorizontalHeaderLabels(
            [self._t(key) for key in RESULT_COLUMN_KEYS]
        )
        self._result_table.verticalHeader().setVisible(False)
        self._result_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._result_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self._result_table.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self._result_table.setAlternatingRowColors(True)
        header = self._result_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for column in (1, 2, 3, 4):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self._result_table, 1)

        self._clear_results()
        return page

    def _build_logs_tab(self) -> QWidget:
        page = QWidget()
        page.setObjectName("ScanLogsPage")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 22, 24, 22)
        layout.setSpacing(10)

        description = QLabel(self._t("logs.description"))
        description.setObjectName("Muted")
        description.setWordWrap(True)
        layout.addWidget(description)

        self._log_view = QPlainTextEdit()
        self._log_view.setObjectName("LogView")
        self._log_view.setReadOnly(True)
        self._log_view.setUndoRedoEnabled(False)
        self._log_view.setMaximumBlockCount(5000)
        self._log_view.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self._log_view.setPlaceholderText(self._t("logs.placeholder"))
        layout.addWidget(self._log_view, 1)

        for entry in self._log_entries:
            self._append_log_entry(entry)
        return page

    @staticmethod
    def _build_label_row(text: str, required: bool = False) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(4)
        if required:
            mark = QLabel("*")
            mark.setObjectName("RequiredMark")
            row.addWidget(mark)
        label = QLabel(text)
        label.setObjectName("FieldLabel")
        row.addWidget(label)
        row.addStretch(1)
        return row

    def _build_yes_no_combo(self) -> QComboBox:
        combo = QComboBox()
        combo.addItem(self._t("common.yes"), True)
        combo.addItem(self._t("common.no"), False)
        combo.setCurrentIndex(1)
        combo.setFixedWidth(110)
        return combo

    @staticmethod
    def _build_combo_row(text: str, combo: QComboBox) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(10)
        label = QLabel(text)
        label.setObjectName("FieldLabel")
        row.addWidget(label)
        row.addStretch(1)
        row.addWidget(combo)
        return row

    def _build_status_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("Card")

        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(10)

        title = QLabel(self._t("environment.title"))
        title.setObjectName("CardTitle")
        layout.addWidget(title)

        rustscan = resolve_rustscan()
        rustscan_text = (
            str(rustscan)
            if rustscan
            else self._t("environment.rustscan_missing")
        )
        state = (
            self._t("environment.ready")
            if rustscan
            else self._t("environment.missing")
        )

        rows = (
            ("Python", platform.python_version()),
            (self._t("environment.qt_bindings"), f"PySide6 {PySide6.__version__}"),
            ("RustScan", f"{rustscan_text} ({state})"),
            (self._t("environment.project_dir"), str(self._store.root)),
            (self._t("environment.app_dir"), str(PROJECT_ROOT)),
        )

        for key, value in rows:
            row = QHBoxLayout()
            row.setSpacing(16)
            key_label = QLabel(key)
            key_label.setObjectName("KeyLabel")
            key_label.setFixedWidth(88)
            value_label = QLabel(value)
            value_label.setObjectName("ValueLabel")
            value_label.setWordWrap(True)
            value_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            row.addWidget(key_label)
            row.addWidget(value_label, 1)
            layout.addLayout(row)

        return card

    def _reload_tree(self, select_path: Path | str | None = None) -> None:
        self._remember_scan_form()
        target = Path(select_path) if select_path else None
        load_error = ""

        self._tree.blockSignals(True)
        self._tree.clear()
        try:
            projects = self._store.load()
        except OSError as exc:
            projects = []
            load_error = str(exc)

        for project in projects:
            project_item = QTreeWidgetItem([project.name])
            project_item.setIcon(0, self._project_icon)
            project_item.setData(0, KIND_ROLE, KIND_PROJECT)
            project_item.setData(0, PATH_ROLE, str(project.path))
            project_item.setToolTip(0, str(project.path))
            self._tree.addTopLevelItem(project_item)

            for scan in project.scans:
                scan_item = QTreeWidgetItem([scan.name])
                scan_item.setIcon(0, self._scan_icon)
                scan_item.setData(0, KIND_ROLE, KIND_SCAN)
                scan_item.setData(0, PATH_ROLE, str(scan.path))
                scan_item.setToolTip(0, str(scan.path))
                project_item.addChild(scan_item)

            project_item.setExpanded(True)

        self._tree.blockSignals(False)

        if target is not None:
            self._select_path(target)
        elif self._tree.currentItem() is None:
            self._show_welcome_page()
        if load_error:
            self._set_status(
                self._t("status.load_failed", error=load_error),
                8000,
                level="ERROR",
            )

    def _select_path(self, path: Path) -> None:
        item = self._find_item(path)
        if item is None:
            return
        parent = item.parent()
        if parent is not None:
            parent.setExpanded(True)
        self._tree.setCurrentItem(item)
        self._tree.scrollToItem(item)

    def _find_item(self, path: Path) -> QTreeWidgetItem | None:
        target = str(path)

        def walk(item: QTreeWidgetItem) -> QTreeWidgetItem | None:
            if item.data(0, PATH_ROLE) == target:
                return item
            for index in range(item.childCount()):
                found = walk(item.child(index))
                if found is not None:
                    return found
            return None

        for index in range(self._tree.topLevelItemCount()):
            found = walk(self._tree.topLevelItem(index))
            if found is not None:
                return found
        return None

    def _create_project(self) -> None:
        try:
            project = self._store.create_project(self._t("project.default_name"))
        except OSError as exc:
            QMessageBox.critical(
                self,
                self._t("dialog.new_project_failed"),
                self._t("dialog.cannot_create_project", error=exc),
            )
            return

        self._reload_tree(project.path)
        self._set_status(
            self._t(
                "status.project_created",
                name=project.name,
                path=project.path,
            ),
            5000,
        )

    def _create_scan(self) -> None:
        item = self._tree.currentItem()
        if item is None:
            QMessageBox.information(
                self,
                self._t("dialog.new_scan_title"),
                self._t("dialog.select_project_first"),
            )
            return

        project_item = item if self._kind(item) == KIND_PROJECT else item.parent()
        if project_item is None or self._kind(project_item) != KIND_PROJECT:
            QMessageBox.information(
                self,
                self._t("dialog.new_scan_title"),
                self._t("dialog.select_project_first"),
            )
            return

        project_name = project_item.text(0)
        project_path = Path(project_item.data(0, PATH_ROLE))
        try:
            scan = self._store.create_scan(
                project_path,
                self._t("scan.default_name"),
            )
        except OSError as exc:
            QMessageBox.critical(
                self,
                self._t("dialog.new_scan_failed"),
                self._t("dialog.cannot_create_scan", error=exc),
            )
            return

        self._reload_tree(scan.path)
        self._set_status(
            self._t(
                "status.scan_created",
                project=project_name,
                name=scan.name,
            ),
            5000,
        )

    def _on_selection_changed(self) -> None:
        self._update_status_for_selection()
        self._update_detail_page()

    def _on_tree_item_clicked(self, _item: QTreeWidgetItem, _column: int) -> None:
        self._update_detail_page()

    def _update_detail_page(self) -> None:
        item = self._tree.currentItem()
        if item is None or self._kind(item) != KIND_SCAN:
            self._show_welcome_page()
            return
        scan = ScanNode(name=item.text(0), path=Path(item.data(0, PATH_ROLE)))
        self._show_scan_page(scan)

    def _show_welcome_page(self) -> None:
        if self._stack.currentWidget() is not self._welcome_page:
            self._remember_scan_form()
        self._current_scan = None
        self._stack.setCurrentWidget(self._welcome_page)

    def _show_settings_page(self) -> None:
        if self._stack.currentWidget() is not self._settings_page:
            self._remember_scan_form()
        self._stack.setCurrentWidget(self._settings_page)
        self._view_sidebar_action.setChecked(False)

    def _show_main_interface(self) -> None:
        self._view_sidebar_action.setChecked(True)
        item = self._tree.currentItem()
        if item is not None and self._kind(item) == KIND_SCAN:
            self._update_detail_page()
        else:
            self._show_welcome_page()
        self.statusBar().showMessage(self._t("status.ready"))

    def _on_language_combo_changed(self, index: int) -> None:
        code = self._language_combo.itemData(index)
        if not code or code == self._language_store.current_code:
            return
        try:
            language = self._language_store.select(str(code))
        except KeyError:
            return
        self._rebuild_ui()
        config_error = self._save_language_config()
        if config_error is not None:
            self._set_status(
                self._t("status.config_save_failed", error=config_error),
                8000,
                level="ERROR",
            )
        else:
            self._set_status(
                self._t("status.language_changed", language=language.name),
                5000,
            )

    def _on_display_mode_combo_changed(self, index: int) -> None:
        mode = self._display_mode_combo.itemData(index)
        if mode not in (DISPLAY_MODE_LIGHT, DISPLAY_MODE_DARK, DISPLAY_MODE_SYSTEM):
            return
        if mode == self._display_mode:
            return

        self._display_mode = str(mode)
        self._apply_theme()
        config_error = self._save_display_mode_config()
        if config_error is not None:
            self._set_status(
                self._t("status.display_config_save_failed", error=config_error),
                8000,
                level="ERROR",
            )
        else:
            self._set_status(
                self._t(
                    "status.display_mode_changed",
                    mode=self._display_mode_combo.currentText(),
                ),
                5000,
            )

    def _on_nmap_path_changed(self) -> None:
        value = self._nmap_path_edit.text().strip().strip('"')
        value = value or DEFAULT_NMAP_PATH
        self._nmap_path_edit.setText(value)
        if value == self._nmap_path:
            return

        self._nmap_path = value
        self._runner.set_nmap_path(value)
        config_error = self._save_nmap_path_config()
        if config_error is not None:
            self._set_status(
                self._t("status.nmap_config_save_failed", error=config_error),
                8000,
                level="ERROR",
            )
        else:
            self._set_status(
                self._t("status.nmap_path_saved", path=value),
                5000,
            )

    def _rebuild_ui(self) -> None:
        selected_item = self._tree.currentItem()
        selected_path = (
            Path(selected_item.data(0, PATH_ROLE))
            if selected_item is not None
            else None
        )
        selected_kind = self._kind(selected_item) if selected_item is not None else ""
        showing_settings = self._stack.currentWidget() is self._settings_page
        settings_section = self._settings_stack.currentIndex()
        showing_scripts = self._stack.currentWidget() is self._scripts_page
        selected_script = ""
        if showing_scripts:
            script_item = self._script_list.currentItem()
            selected_script = script_item.text() if script_item is not None else ""
        showing_scan = self._stack.currentWidget() is self._scan_page
        tab_index = self._tabs.currentIndex()
        sidebar_visible = self._view_sidebar_action.isChecked()

        self._remember_scan_form()
        self._current_scan = None
        old_central = self.takeCentralWidget()
        self.menuBar().clear()

        self._build_ui()
        self._build_menus()
        self._reload_tree(selected_path)

        if showing_settings:
            self._show_settings_page()
            self._show_settings_section(settings_section)
        elif showing_scripts:
            self._show_scripts_page()
            if selected_script:
                self._refresh_script_list(select=selected_script)
        elif showing_scan and selected_kind == KIND_SCAN:
            self._tabs.setCurrentIndex(tab_index)

        self._set_sidebar_visible(sidebar_visible)
        if old_central is not None:
            old_central.deleteLater()
        self.statusBar().showMessage(self._t("status.ready"))

    def _show_scan_page(self, scan: ScanNode) -> None:
        same_scan = self._current_scan is not None and self._current_scan.path == scan.path
        if not same_scan:
            self._remember_scan_form()
            self._current_scan = scan
            self._load_scan_form(scan)
            self._clear_results()
        else:
            self._current_scan = scan

        self._scan_title.setText(scan.name)
        self._scan_path_label.setText(str(scan.path))
        self._stack.setCurrentWidget(self._scan_page)
        if self._tabs.currentIndex() == 1:
            self._refresh_results()

    def _remember_scan_form(self) -> None:
        if self._current_scan is None:
            return
        values: dict[str, object] = {
            "address": self._address_edit.text(),
            "address_file_mode": self._combo_value(self._address_file_mode),
            "address_file": self._address_file_edit.text(),
            "exclude_ip_mode": self._combo_value(self._exclude_ip_mode),
            "exclude_ips": self._exclude_ip_edit.text(),
            "mode": self._port_mode.currentData(),
            "ports": self._ports_edit.text(),
            "attack_type": str(self._attack_type_combo.currentData()),
            "exclude_mode": self._combo_value(self._exclude_mode),
            "exclude_ports": self._exclude_ports_edit.text(),
            "ignore_config": self._combo_value(self._ignore_config_combo),
            "udp_mode": self._combo_value(self._udp_mode_combo),
            "use_nmap": self._combo_value(self._nmap_version_combo),
            "nmap_extra_args": self._nmap_extra_args_edit.text(),
            "use_script": self._combo_value(self._use_script_combo),
            "script_name": str(self._scan_script_combo.currentData() or ""),
        }
        self._form_cache[str(self._current_scan.path)] = values
        try:
            save_scan_form(self._current_scan.path, values)
        except FileNotFoundError:
            pass
        except OSError as exc:
            self._append_log(
                "WARN",
                self._t("log.scan_info_save_failed", error=exc),
            )

    def _load_scan_form(self, scan: ScanNode) -> None:
        cached = self._form_cache.get(str(scan.path))
        if cached is None:
            cached = load_scan_form(scan.path)
            if cached:
                self._form_cache[str(scan.path)] = cached
        values = cached or {}
        mode = values.get("mode", PORT_MODE_PORTS)
        if mode not in {PORT_MODE_PORTS, PORT_MODE_RANGE, PORT_MODE_FILE}:
            mode = PORT_MODE_PORTS
        self._address_edit.setText(values.get("address", ""))
        self._set_yes_no_combo(
            self._address_file_mode, values.get("address_file_mode", False)
        )
        self._address_file_edit.setText(str(values.get("address_file", "")))
        self._update_address_file_enabled(
            bool(self._combo_value(self._address_file_mode))
        )
        self._set_combo_data(self._port_mode, mode)
        self._update_port_mode_controls(mode)
        self._ports_edit.setText(values.get("ports", ""))
        attack_type = str(values.get("attack_type", ATTACK_SNIPER))
        if attack_type not in ATTACK_TYPES:
            attack_type = ATTACK_SNIPER
        self._set_combo_data(self._attack_type_combo, attack_type)
        self._update_attack_type_visibility()
        self._set_yes_no_combo(
            self._exclude_ip_mode, values.get("exclude_ip_mode", False)
        )
        self._exclude_ip_edit.setText(values.get("exclude_ips", ""))
        self._update_exclude_ip_enabled(self._combo_value(self._exclude_ip_mode))
        self._set_yes_no_combo(
            self._ignore_config_combo, values.get("ignore_config", False)
        )
        self._set_yes_no_combo(
            self._udp_mode_combo, values.get("udp_mode", False)
        )
        self._set_yes_no_combo(
            self._nmap_version_combo, values.get("use_nmap", False)
        )
        self._nmap_extra_args_edit.setText(values.get("nmap_extra_args", ""))
        self._update_nmap_extra_enabled(self._combo_value(self._nmap_version_combo))
        self._refresh_scan_script_combo(str(values.get("script_name", "")))
        self._set_yes_no_combo(
            self._use_script_combo, values.get("use_script", False)
        )
        self._update_script_enabled(bool(self._use_script_combo.currentData()))
        self._set_yes_no_combo(
            self._exclude_mode, values.get("exclude_mode", False)
        )
        self._exclude_ports_edit.setText(values.get("exclude_ports", ""))
        self._update_exclude_enabled(self._combo_value(self._exclude_mode))

    @staticmethod
    def _combo_value(combo: QComboBox) -> bool | str:
        return combo.currentData()

    @staticmethod
    def _set_combo_data(combo: QComboBox, value: object) -> None:
        combo.blockSignals(True)
        index = combo.findData(value)
        combo.setCurrentIndex(index if index >= 0 else 0)
        combo.blockSignals(False)

    @classmethod
    def _set_yes_no_combo(cls, combo: QComboBox, value: object) -> None:
        selected = value if isinstance(value, bool) else False
        cls._set_combo_data(combo, selected)

    @staticmethod
    def _split_addresses(value: str) -> list[str]:
        addresses: list[str] = []
        seen: set[str] = set()
        for part in re.split(r"[,\n;]+", value):
            address = part.strip()
            key = address.casefold()
            if not address or key in seen:
                continue
            seen.add(key)
            addresses.append(address)
        return addresses

    @classmethod
    def _merge_addresses(cls, values: list[str]) -> str:
        merged: list[str] = []
        for value in values:
            merged.extend(cls._split_addresses(value))
        return ",".join(merged)

    def _apply_paired_address_file(self, path: str, count: int) -> None:
        self._set_combo_data(self._port_mode, PORT_MODE_FILE)
        self._update_port_mode_controls(PORT_MODE_FILE)
        self._ports_edit.setText(path)
        self._set_combo_data(self._attack_type_combo, ATTACK_PITCHFORK)
        self._update_attack_type_visibility()
        self._append_log(
            "INFO",
            self._t("log.auto_address_port_mode", count=count),
        )

    def _on_port_mode_changed(self, _index: int) -> None:
        self._ports_edit.clear()
        self._update_port_mode_controls(self._port_mode.currentData())
        self._update_attack_type_visibility()

    def _update_port_mode_controls(self, mode: str) -> None:
        is_file = mode == PORT_MODE_FILE
        self._ports_file_button.setEnabled(is_file)
        if is_file:
            self._ports_edit.setPlaceholderText(
                self._t("scan.ports_placeholder_file")
            )
        elif mode == PORT_MODE_RANGE:
            self._ports_edit.setPlaceholderText(
                self._t("scan.ports_placeholder_range")
            )
        else:
            self._ports_edit.setPlaceholderText(
                self._t("scan.ports_placeholder_ports")
            )

    def _on_address_file_mode_changed(self, _index: int) -> None:
        enabled = bool(self._address_file_mode.currentData())
        self._update_address_file_enabled(enabled)
        self._update_attack_type_visibility()
        if enabled:
            self._address_file_edit.setFocus()
        else:
            self._address_edit.setFocus()

    def _update_address_file_enabled(self, enabled: bool) -> None:
        self._address_edit.setEnabled(not enabled)
        self._address_file_edit.setEnabled(enabled)
        self._address_file_button.setEnabled(enabled)

    def _update_attack_type_visibility(self) -> None:
        visible = (
            bool(self._address_file_mode.currentData())
            and self._port_mode.currentData() == PORT_MODE_FILE
        )
        self._attack_type_widget.setVisible(visible)

    def _choose_address_file(self) -> None:
        current = self._address_file_edit.text().strip()
        start_dir = (
            str(Path(current).parent)
            if current and Path(current).parent.is_dir()
            else str(Path.home())
        )
        path, _selected_filter = QFileDialog.getOpenFileName(
            self,
            self._t("dialog.choose_address_file"),
            start_dir,
            self._t("dialog.address_file_filter"),
        )
        if not path:
            return

        self._address_file_edit.setText(path)
        try:
            data = load_address_file(path)
        except OSError as exc:
            message = self._t("dialog.address_file_read_failed", error=exc)
            self._append_log("ERROR", message)
            QMessageBox.critical(
                self,
                self._t("dialog.address_file_failed"),
                message,
            )
            self._address_file_edit.setFocus()
            return
        except AddressFileError as exc:
            message = self._address_file_error_message(exc)
            self._append_log("WARN", message)
            QMessageBox.warning(
                self,
                self._t("dialog.address_file_failed"),
                message,
            )
            self._address_file_edit.setFocus()
            return

        if data.has_ports:
            self._set_combo_data(self._port_mode, PORT_MODE_FILE)
            self._update_port_mode_controls(PORT_MODE_FILE)
            self._ports_edit.setText(path)
            self._set_combo_data(self._attack_type_combo, ATTACK_PITCHFORK)
            self._update_attack_type_visibility()
            self._set_status(
                self._t(
                    "status.address_port_file_loaded",
                    count=len(data.pairs),
                    name=Path(path).name,
                ),
                5000,
            )
        else:
            self._set_status(
                self._t(
                    "status.address_file_loaded",
                    count=len(data.addresses),
                    name=Path(path).name,
                ),
                5000,
            )

    def _choose_port_file(self) -> None:
        current = self._ports_edit.text().strip()
        start_dir = (
            str(Path(current).parent)
            if current and Path(current).parent.is_dir()
            else str(Path.home())
        )
        path, _selected_filter = QFileDialog.getOpenFileName(
            self,
            self._t("dialog.choose_port_file"),
            start_dir,
            self._t("dialog.port_file_filter"),
        )
        if not path:
            return

        self._ports_edit.setText(path)
        try:
            ports = load_ports(path)
        except OSError as exc:
            message = self._t("dialog.port_file_read_failed", error=exc)
            self._append_log("ERROR", message)
            QMessageBox.critical(
                self,
                self._t("dialog.port_file_failed"),
                message,
            )
            self._ports_edit.setFocus()
            return
        except PortFileError as exc:
            message = self._port_file_error_message(exc)
            self._append_log("WARN", message)
            QMessageBox.warning(
                self,
                self._t("dialog.port_file_failed"),
                message,
            )
            self._ports_edit.setFocus()
            return

        self._set_status(
            self._t(
                "status.port_file_loaded",
                count=len(ports),
                name=Path(path).name,
            ),
            5000,
        )

    def _address_file_error_message(self, error: AddressFileError) -> str:
        if isinstance(error, UnsupportedAddressFileError):
            return self._t("dialog.address_file_unsupported")
        if isinstance(error, AddressColumnNotFoundError):
            return self._t("dialog.address_file_no_column")
        if isinstance(error, EmptyAddressFileError):
            return self._t("dialog.address_file_empty")
        return self._t("dialog.address_file_read_failed", error=error)

    def _port_file_error_message(self, error: PortFileError) -> str:
        if isinstance(error, UnsupportedPortFileError):
            return self._t("dialog.port_file_unsupported")
        if isinstance(error, PortColumnNotFoundError):
            return self._t("dialog.port_file_no_column")
        if isinstance(error, EmptyPortFileError):
            return self._t("dialog.port_file_empty")
        return self._t("dialog.port_file_read_failed", error=error)

    def _on_exclude_ip_mode_changed(self, _index: int) -> None:
        enabled = bool(self._exclude_ip_mode.currentData())
        self._update_exclude_ip_enabled(enabled)
        if enabled:
            self._exclude_ip_edit.setFocus()

    def _update_exclude_ip_enabled(self, enabled: bool) -> None:
        self._exclude_ip_edit.setEnabled(enabled)

    def _on_exclude_mode_changed(self, _index: int) -> None:
        enabled = bool(self._exclude_mode.currentData())
        self._update_exclude_enabled(enabled)
        if enabled:
            self._exclude_ports_edit.setFocus()

    def _update_exclude_enabled(self, enabled: bool) -> None:
        self._exclude_ports_edit.setEnabled(enabled)

    def _on_nmap_version_mode_changed(self, _index: int) -> None:
        enabled = bool(self._nmap_version_combo.currentData())
        self._update_nmap_extra_enabled(enabled)
        if enabled:
            self._nmap_extra_args_edit.setFocus()

    def _update_nmap_extra_enabled(self, enabled: bool) -> None:
        self._nmap_extra_args_edit.setEnabled(enabled)

    def _refresh_scan_script_combo(self, selected: str | None = None) -> None:
        if not hasattr(self, "_scan_script_combo"):
            return
        current = (
            selected
            if selected is not None
            else str(self._scan_script_combo.currentData() or "")
        )
        names = self._script_store.list_scripts()
        self._scan_script_combo.blockSignals(True)
        self._scan_script_combo.clear()
        for name in names:
            self._scan_script_combo.addItem(name, name)
        if not names:
            self._scan_script_combo.addItem(
                self._t("scan.no_scripts_available"),
                "",
            )
        index = self._scan_script_combo.findData(current)
        self._scan_script_combo.setCurrentIndex(index if index >= 0 else 0)
        self._scan_script_combo.blockSignals(False)
        self._update_script_enabled(bool(self._use_script_combo.currentData()))

    def _on_use_script_mode_changed(self, _index: int) -> None:
        enabled = bool(self._use_script_combo.currentData())
        if enabled:
            self._refresh_scan_script_combo()
        else:
            self._update_script_enabled(False)
        if enabled and self._scan_script_combo.isEnabled():
            self._scan_script_combo.setFocus()

    def _update_script_enabled(self, enabled: bool) -> None:
        has_scripts = any(
            bool(self._scan_script_combo.itemData(index))
            for index in range(self._scan_script_combo.count())
        )
        self._scan_script_combo.setEnabled(enabled and has_scripts)

    def _on_tab_changed(self, index: int) -> None:
        self._remember_scan_form()
        if index == 1:
            self._refresh_results()

    def _start_scan(self) -> None:
        if self._runner.is_running or self._current_scan is None:
            return

        address_mode = bool(self._address_file_mode.currentData())
        pairs: tuple[tuple[str, int], ...] = ()
        if address_mode:
            address_file = self._address_file_edit.text().strip()
            if not address_file:
                message = self._t("dialog.address_file_required")
                self._append_log("WARN", message)
                QMessageBox.warning(
                    self,
                    self._t("dialog.cannot_start_scan"),
                    message,
                )
                self._address_file_edit.setFocus()
                return
            try:
                data = load_address_file(address_file)
            except OSError as exc:
                message = self._t("dialog.address_file_read_failed", error=exc)
                self._append_log("ERROR", message)
                QMessageBox.critical(
                    self,
                    self._t("dialog.cannot_start_scan"),
                    message,
                )
                self._address_file_edit.setFocus()
                return
            except AddressFileError as exc:
                message = self._address_file_error_message(exc)
                self._append_log("WARN", message)
                QMessageBox.warning(
                    self,
                    self._t("dialog.cannot_start_scan"),
                    message,
                )
                self._address_file_edit.setFocus()
                return
            addresses = list(data.addresses)
            if data.has_ports:
                pairs = data.pairs
                already_using_file = (
                    self._port_mode.currentData() == PORT_MODE_FILE
                    and Path(self._ports_edit.text().strip()) == Path(address_file)
                )
                if not already_using_file:
                    self._apply_paired_address_file(address_file, len(pairs))
        else:
            addresses = self._split_addresses(self._address_edit.text())

        if not addresses:
            self._append_log("WARN", self._t("dialog.address_required"))
            QMessageBox.warning(
                self,
                self._t("dialog.cannot_start_scan"),
                self._t("dialog.address_required"),
            )
            if address_mode:
                self._address_file_edit.setFocus()
            else:
                self._address_edit.setFocus()
            return

        use_script = bool(self._use_script_combo.currentData())
        script_path = ""
        if use_script:
            script_name = str(self._scan_script_combo.currentData() or "")
            candidate = self._script_store.root / script_name if script_name else None
            if candidate is None or not candidate.is_file():
                self._append_log("WARN", self._t("dialog.script_unavailable"))
                QMessageBox.warning(
                    self,
                    self._t("dialog.cannot_start_scan"),
                    self._t("dialog.script_unavailable"),
                )
                self._refresh_scan_script_combo()
                self._scan_script_combo.setFocus()
                return
            script_path = str(candidate)

        executable = resolve_rustscan()
        if executable is None:
            self._append_log("ERROR", self._t("dialog.rustscan_missing"))
            QMessageBox.critical(
                self,
                self._t("dialog.cannot_start_scan"),
                self._t("dialog.rustscan_missing"),
            )
            return

        port_mode = self._port_mode.currentData()
        imported_ports: list[int] = []
        ports_text = ""
        port_range = ""
        if not pairs:
            if port_mode == PORT_MODE_FILE:
                port_file = self._ports_edit.text().strip()
                if not port_file:
                    message = self._t("dialog.port_file_required")
                    self._append_log("WARN", message)
                    QMessageBox.warning(
                        self,
                        self._t("dialog.cannot_start_scan"),
                        message,
                    )
                    self._ports_edit.setFocus()
                    return
                try:
                    imported_ports = load_ports(port_file)
                except OSError as exc:
                    message = self._t("dialog.port_file_read_failed", error=exc)
                    self._append_log("ERROR", message)
                    QMessageBox.critical(
                        self,
                        self._t("dialog.cannot_start_scan"),
                        message,
                    )
                    self._ports_edit.setFocus()
                    return
                except PortFileError as exc:
                    message = self._port_file_error_message(exc)
                    self._append_log("WARN", message)
                    QMessageBox.warning(
                        self,
                        self._t("dialog.cannot_start_scan"),
                        message,
                    )
                    self._ports_edit.setFocus()
                    return
            elif port_mode == PORT_MODE_RANGE:
                port_range = self._ports_edit.text().strip()
            else:
                ports_text = self._ports_edit.text().strip()

        attack_type = (
            str(self._attack_type_combo.currentData())
            if address_mode and port_mode == PORT_MODE_FILE
            else ATTACK_SNIPER
        )
        if attack_type not in ATTACK_TYPES:
            attack_type = ATTACK_SNIPER
        jobs = build_scan_jobs(
            addresses,
            pairs=pairs,
            imported_ports=imported_ports,
            port_text=ports_text,
            port_range=port_range,
            attack_type=attack_type,
        )
        if not jobs:
            self._set_status(
                self._t("status.no_valid_scan_targets"),
                8000,
                level="WARN",
            )
            return

        options = ScanOptions(
            address=",".join(addresses),
            exclude_addresses=(
                self._exclude_ip_edit.text().strip()
                if bool(self._exclude_ip_mode.currentData())
                else ""
            ),
            exclude_ports=(
                self._exclude_ports_edit.text().strip()
                if bool(self._exclude_mode.currentData())
                else ""
            ),
            ignore_config=bool(self._ignore_config_combo.currentData()),
            udp=bool(self._udp_mode_combo.currentData()),
            use_nmap=bool(self._nmap_version_combo.currentData()),
            nmap_extra_args=self._nmap_extra_args_edit.text().strip(),
            use_script=use_script,
            script_path=script_path,
        )

        scan_path = self._current_scan.path
        try:
            scan_path.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            self._append_log(
                "ERROR",
                self._t("dialog.cannot_access_scan_dir", error=exc),
            )
            QMessageBox.critical(
                self,
                self._t("dialog.cannot_start_scan"),
                self._t("dialog.cannot_access_scan_dir", error=exc),
            )
            return

        self._remember_scan_form()
        self._scan_jobs = jobs
        self._scan_job_index = 0
        self._scan_base_options = options
        self._scan_executable = executable
        self._scan_results = []
        self._scan_path = scan_path
        self._scan_target_summary = (
            jobs[0].address
            if len(jobs) == 1
            else self._t("status.scan_targets", count=len(jobs))
        )
        self._active_scan_protocol = "udp" if options.udp else "tcp"
        self._flush_scan_output()
        self._start_button.setEnabled(False)
        self._start_next_scan_job()

    def _start_next_scan_job(self) -> None:
        if (
            self._scan_base_options is None
            or self._scan_executable is None
            or self._scan_path is None
            or self._scan_job_index >= len(self._scan_jobs)
        ):
            return

        job = self._scan_jobs[self._scan_job_index]
        options = replace(
            self._scan_base_options,
            address=job.address,
            ports=job.ports,
            port_range=job.port_range,
        )
        arguments = build_rustscan_args(options)
        self._active_scan_path = self._scan_path
        self._active_scan_target = job.address
        if len(self._scan_jobs) > 1:
            self._set_status(
                self._t(
                    "status.scanning_job",
                    current=self._scan_job_index + 1,
                    total=len(self._scan_jobs),
                    target=job.address,
                )
            )
        else:
            self._set_status(self._t("status.scanning", target=job.address))
        self._append_log(
            "INFO",
            self._t(
                "log.scan_command",
                command=(
                    f"{self._scan_executable.name} {' '.join(arguments)}".strip()
                ),
            ),
        )
        self._runner.start(
            self._scan_executable,
            arguments,
            self._scan_path,
        )

    def _on_scan_finished(self, exit_code: int, stdout: str, stderr: str) -> None:
        self._flush_scan_output()
        scan_path = self._scan_path
        target = self._active_scan_target
        protocol = self._active_scan_protocol

        if exit_code != 0:
            details = (stderr or stdout).strip()
            if len(details) > 4000:
                details = details[:4000] + "\n…"
            if not details:
                details = self._t("dialog.scan_no_details")
            self._reset_scan_queue()
            QMessageBox.critical(
                self,
                self._t("dialog.scan_failed"),
                self._t(
                    "dialog.scan_failed_detail",
                    code=exit_code,
                    details=details,
                ),
            )
            self._set_status(
                self._t("status.scan_failed_code", code=exit_code),
                8000,
                level="ERROR",
            )
            return

        if scan_path is None:
            self._reset_scan_queue()
            self._set_status(
                self._t("status.scan_no_scan_dir"),
                8000,
                level="WARN",
            )
            return

        results = parse_rustscan_output(
            stdout,
            protocol=protocol,
            target=target or "",
        )
        self._scan_results.extend(results)
        self._scan_job_index += 1
        if self._scan_job_index < len(self._scan_jobs):
            self._start_next_scan_job()
            return

        final_results = self._merge_port_results(self._scan_results)
        target_summary = self._scan_target_summary
        result_filename = datetime.now().strftime("result-%Y-%m-%d-%H-%M-%S.xml")
        try:
            result_path = save_results(
                scan_path,
                final_results,
                target=target_summary,
                filename=result_filename,
                job_count=len(self._scan_jobs) if len(self._scan_jobs) > 1 else None,
            )
        except OSError as exc:
            self._reset_scan_queue()
            QMessageBox.critical(
                self,
                self._t("dialog.save_results_failed"),
                self._t("dialog.cannot_write_scan_dir", error=exc),
            )
            self._set_status(
                self._t("status.scan_save_failed"),
                8000,
                level="ERROR",
            )
            return

        self._reset_scan_queue()
        self._result_cache.pop(str(scan_path), None)
        if self._current_scan is not None and self._current_scan.path == scan_path:
            self._refresh_results()
            self._tabs.setCurrentIndex(1)

        self._set_status(
            self._t(
                "status.scan_completed",
                count=len(final_results),
                path=result_path,
            ),
            10000,
        )
        QMessageBox.information(
            self,
            self._t("dialog.scan_completed"),
            self._t(
                "dialog.scan_completed_body",
                target=target_summary,
                count=len(final_results),
                path=result_path,
            ),
        )

    def _reset_scan_queue(self) -> None:
        self._scan_jobs = []
        self._scan_job_index = 0
        self._scan_base_options = None
        self._scan_executable = None
        self._scan_results = []
        self._scan_path = None
        self._active_scan_path = None
        self._active_scan_target = ""
        self._scan_target_summary = ""
        self._start_button.setEnabled(True)

    @staticmethod
    def _merge_port_results(results: list[PortResult]) -> list[PortResult]:
        unique: list[PortResult] = []
        index_by_key: dict[tuple[str, str, str], int] = {}
        for result in results:
            key = (result.address, result.port, result.protocol)
            existing_index = index_by_key.get(key)
            if existing_index is None:
                index_by_key[key] = len(unique)
                unique.append(result)
                continue
            existing = unique[existing_index]
            if result.service:
                existing.service = result.service
            if result.version:
                existing.version = result.version
            if result.state and not existing.state:
                existing.state = result.state
        return unique

    def _on_scan_failed_to_start(self, error: str) -> None:
        self._reset_scan_queue()
        QMessageBox.critical(
            self,
            self._t("dialog.scan_start_failed"),
            self._t("dialog.cannot_start_rustscan", error=error),
        )
        self._set_status(
            self._t("status.scan_start_failed"),
            8000,
            level="ERROR",
        )

    def _clear_results(self) -> None:
        self._result_documents = []
        self._result_file_combo.blockSignals(True)
        self._result_file_combo.clear()
        self._result_file_combo.setEnabled(False)
        self._result_file_combo.blockSignals(False)
        self._export_csv_button.setEnabled(False)
        self._result_table.setRowCount(0)
        self._result_table.setVisible(False)
        self._result_hint.setText(self._t("results.empty_hint"))

    def _refresh_results(self) -> None:
        if self._current_scan is None:
            return

        cache_key = str(self._current_scan.path)
        documents = self._result_cache.get(cache_key)
        if documents is None:
            documents = load_result_documents(self._current_scan.path)
            self._result_cache[cache_key] = documents
        self._result_documents = documents
        self._result_file_combo.blockSignals(True)
        self._result_file_combo.clear()
        for document in documents:
            self._result_file_combo.addItem(document.path.name)
            self._result_file_combo.setItemData(
                self._result_file_combo.count() - 1,
                str(document.path),
                Qt.ItemDataRole.ToolTipRole,
            )
        self._result_file_combo.setEnabled(bool(documents))
        self._result_file_combo.blockSignals(False)

        if not documents:
            self._export_csv_button.setEnabled(False)
            self._result_table.setRowCount(0)
            self._result_table.setVisible(False)
            self._result_hint.setText(self._t("results.empty_hint"))
            return

        self._result_file_combo.setCurrentIndex(0)
        self._render_result_document(0)

    def _reload_results(self) -> None:
        if self._current_scan is None:
            return
        self._result_cache.pop(str(self._current_scan.path), None)
        self._refresh_results()

    def _on_result_file_changed(self, index: int) -> None:
        self._render_result_document(index)

    def _render_result_document(self, index: int) -> None:
        if not 0 <= index < len(self._result_documents):
            return

        document = self._result_documents[index]
        if document.error:
            self._export_csv_button.setEnabled(False)
            self._result_table.setRowCount(0)
            self._result_table.setVisible(False)
            self._result_hint.setText(
                self._t(
                    "results.parse_error",
                    filename=document.path.name,
                    error=document.error,
                )
            )
            return

        results = document.results
        self._export_csv_button.setEnabled(bool(results))
        self._result_table.setRowCount(len(results))
        for row_index, result in enumerate(results):
            values = (
                result.address,
                result.port,
                result.protocol,
                result.state,
                result.service,
                result.version,
            )
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setToolTip(value)
                self._result_table.setItem(row_index, column, item)

        self._result_table.setVisible(bool(results))
        if results:
            target = self._result_target_text(document)
            if target:
                hint = self._t(
                    "results.summary_with_target",
                    filename=document.path.name,
                    target=target,
                    count=len(results),
                )
            else:
                hint = self._t(
                    "results.summary",
                    filename=document.path.name,
                    count=len(results),
                )
            self._result_hint.setText(hint)
        else:
            self._result_hint.setText(
                self._t(
                    "results.no_results_in_file",
                    filename=document.path.name,
                )
            )

    def _result_target_text(self, document: ResultDocument) -> str:
        if document.job_count and document.job_count > 1:
            return self._t("status.scan_targets", count=document.job_count)
        return document.target

    def _export_current_results_csv(self) -> None:
        index = self._result_file_combo.currentIndex()
        if not 0 <= index < len(self._result_documents):
            self._warn_no_results_to_export()
            return

        document = self._result_documents[index]
        if document.error or not document.results:
            self._warn_no_results_to_export()
            return

        default_path = document.path.with_suffix(".csv")
        selected_path, _selected_filter = QFileDialog.getSaveFileName(
            self,
            self._t("results.export_dialog_title"),
            str(default_path),
            self._t("results.export_filter"),
        )
        if not selected_path:
            return

        csv_path = Path(selected_path)
        if not csv_path.suffix:
            csv_path = csv_path.with_suffix(".csv")
        try:
            with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerow([self._t(key) for key in RESULT_COLUMN_KEYS])
                for result in document.results:
                    writer.writerow(
                        (
                            result.address,
                            result.port,
                            result.protocol,
                            result.state,
                            result.service,
                            result.version,
                        )
                    )
        except OSError as exc:
            message = self._t("dialog.cannot_write_csv", error=exc)
            self._append_log("ERROR", message)
            QMessageBox.critical(
                self,
                self._t("dialog.csv_export_failed"),
                message,
            )
            return

        self._set_status(
            self._t(
                "status.csv_exported",
                count=len(document.results),
                path=csv_path,
            ),
            8000,
        )

    def _warn_no_results_to_export(self) -> None:
        message = self._t("results.export_no_results")
        self._append_log("WARN", message)
        QMessageBox.warning(
            self,
            self._t("dialog.csv_export_failed"),
            message,
        )

    def _show_context_menu(self, position) -> None:
        item = self._tree.itemAt(position)
        if item is None:
            return

        self._tree.setCurrentItem(item)
        kind = self._kind(item)
        menu = QMenu(self)

        new_scan_action = None
        if kind == KIND_PROJECT:
            new_scan_action = menu.addAction(self._t("context.new_scan"))
            menu.addSeparator()

        rename_action = menu.addAction(self._t("context.rename"))
        open_action = menu.addAction(self._t("context.open_explorer"))
        menu.addSeparator()
        delete_action = menu.addAction(self._t("context.delete"))
        chosen = menu.exec(self._tree.viewport().mapToGlobal(position))

        if chosen is None:
            return
        if chosen is new_scan_action:
            self._create_scan()
        elif chosen is rename_action:
            self._rename_item(item)
        elif chosen is open_action:
            self._open_in_explorer(item)
        elif chosen is delete_action:
            self._delete_item(item)

    def _rename_selected(self) -> None:
        item = self._tree.currentItem()
        if item is None:
            self.statusBar().showMessage(self._t("status.select_item_to_rename"), 5000)
            return
        self._rename_item(item)

    def _ask_new_name(self, old_name: str) -> tuple[str, bool]:
        return QInputDialog.getText(
            self,
            self._t("dialog.rename"),
            self._t("dialog.new_name"),
            text=old_name,
        )

    def _rename_item(self, item: QTreeWidgetItem) -> None:
        kind = self._kind(item)
        if kind not in {KIND_PROJECT, KIND_SCAN}:
            return

        old_name = item.text(0)
        new_name, accepted = self._ask_new_name(old_name)
        if not accepted:
            return

        path = Path(item.data(0, PATH_ROLE))
        try:
            if kind == KIND_PROJECT:
                new_node = self._store.rename_project(
                    ProjectNode(name=old_name, path=path), new_name
                )
            else:
                new_node = self._store.rename_scan(
                    ScanNode(name=old_name, path=path), new_name
                )
        except InvalidNameError:
            QMessageBox.warning(
                self,
                self._t("dialog.invalid_name"),
                self._t("dialog.invalid_name_message"),
            )
            return
        except NameConflictError:
            QMessageBox.warning(
                self,
                self._t("dialog.rename_failed"),
                self._t("dialog.name_conflict_message"),
            )
            return
        except OSError as exc:
            QMessageBox.critical(
                self,
                self._t("dialog.rename_failed"),
                self._t("dialog.cannot_rename_folder", error=exc),
            )
            return

        self._migrate_form_cache(path, new_node.path)
        self._reload_tree(new_node.path)
        self._set_status(
            self._t(
                "status.renamed",
                old_name=old_name,
                new_name=new_node.name,
            ),
            5000,
        )

    def _migrate_form_cache(self, old_path: Path, new_path: Path) -> None:
        old_prefix = str(old_path)
        new_prefix = str(new_path)
        for key in list(self._form_cache):
            if key == old_prefix or key.startswith(old_prefix + "\\") or key.startswith(
                old_prefix + "/"
            ):
                suffix = key[len(old_prefix):]
                self._form_cache[new_prefix + suffix] = self._form_cache.pop(key)

    def _build_delete_dialog(
        self,
        item: QTreeWidgetItem,
    ) -> tuple[QDialog, QCheckBox]:
        dialog = QDialog(self)
        dialog.setObjectName("DeleteDialog")
        dialog.setWindowTitle(self._t("dialog.delete_title"))
        dialog.setModal(True)
        dialog.setMinimumWidth(340)

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(24, 20, 24, 18)
        layout.setSpacing(16)

        title = QLabel(self._t("dialog.delete_title"))
        title.setObjectName("DangerDialogTitle")
        layout.addWidget(title)

        delete_local = QCheckBox(self._t("dialog.delete_local_files"))
        delete_local.setObjectName("DeleteLocalFilesCheckBox")
        delete_local.setChecked(False)
        layout.addWidget(delete_local)

        actions = QHBoxLayout()
        actions.setSpacing(8)
        actions.addStretch(1)

        cancel = QPushButton(self._t("dialog.cancel"))
        cancel.setObjectName("DialogCancelButton")
        cancel.clicked.connect(dialog.reject)
        actions.addWidget(cancel)

        confirm = QPushButton(self._t("dialog.confirm"))
        confirm.setObjectName("DangerButton")
        confirm.setDefault(True)
        confirm.clicked.connect(dialog.accept)
        actions.addWidget(confirm)

        layout.addLayout(actions)
        return dialog, delete_local

    def _confirm_delete(self, item: QTreeWidgetItem) -> bool | None:
        dialog, delete_local = self._build_delete_dialog(item)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return None
        return delete_local.isChecked()

    def _delete_item(self, item: QTreeWidgetItem) -> None:
        kind = self._kind(item)
        if kind not in {KIND_PROJECT, KIND_SCAN}:
            return

        delete_files = self._confirm_delete(item)
        if delete_files is None:
            return

        name = item.text(0)
        path = Path(item.data(0, PATH_ROLE))
        try:
            if kind == KIND_PROJECT:
                self._store.delete_project(path, delete_files=delete_files)
            else:
                self._store.delete_scan(path, delete_files=delete_files)
        except OSError as exc:
            QMessageBox.critical(
                self,
                self._t("dialog.delete_failed"),
                self._t("dialog.cannot_delete_folder", error=exc),
            )
            return

        self._drop_path_caches(path)
        if self._current_scan is not None and self._current_scan.path.is_relative_to(
            path
        ):
            self._current_scan = None
        self._reload_tree()
        self._set_status(
            self._t("status.deleted", name=name),
            5000,
        )

    def _drop_path_caches(self, path: Path) -> None:
        for cache in (self._form_cache, self._result_cache):
            for key in list(cache):
                try:
                    key_path = Path(key)
                except (OSError, ValueError):
                    continue
                if key_path.is_relative_to(path):
                    cache.pop(key, None)

    def _open_in_explorer(self, item: QTreeWidgetItem) -> None:
        path = Path(item.data(0, PATH_ROLE))
        try:
            path.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            QMessageBox.critical(
                self,
                self._t("dialog.open_failed"),
                self._t("dialog.cannot_access_folder", error=exc),
            )
            return
        if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(path))):
            QMessageBox.warning(
                self,
                self._t("dialog.open_failed"),
                self._t("dialog.cannot_open_folder", path=path),
            )

    def _hide_sidebar(self) -> None:
        self._view_sidebar_action.setChecked(False)

    def _set_sidebar_visible(self, visible: bool) -> None:
        self._sidebar.setVisible(visible)
        if self._view_sidebar_action.isChecked() != visible:
            self._view_sidebar_action.setChecked(visible)

    def _update_status_for_selection(self) -> None:
        item = self._tree.currentItem()
        if item is None:
            self.statusBar().showMessage(self._t("status.ready"))
            return
        path = item.data(0, PATH_ROLE)
        self.statusBar().showMessage(
            self._t("status.selected", name=item.text(0), path=path)
        )

    def _build_about_dialog(self) -> QDialog:
        dialog = QDialog(self)
        dialog.setObjectName("AboutDialog")
        dialog.setWindowTitle(self._t("dialog.about_title"))
        dialog.setModal(True)

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(32, 24, 32, 20)
        layout.setSpacing(14)

        logo = QLabel()
        logo.setObjectName("AboutLogo")
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo_pixmap = QPixmap(str(LOGO_FILE))
        if not logo_pixmap.isNull():
            logo_pixmap = logo_pixmap.scaledToWidth(
                280,
                Qt.TransformationMode.SmoothTransformation,
            )
            logo.setPixmap(logo_pixmap)
        layout.addWidget(logo, 0, Qt.AlignmentFlag.AlignHCenter)

        info = QVBoxLayout()
        info.setContentsMargins(0, 0, 0, 0)
        info.setSpacing(2)

        name = QLabel(self._t("dialog.about_name"))
        name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        info.addWidget(name)

        description = QLabel(self._t("dialog.about_description"))
        description.setObjectName("AboutDescription")
        description.setAlignment(Qt.AlignmentFlag.AlignCenter)
        info.addWidget(description)

        github_row = QHBoxLayout()
        github_row.setContentsMargins(0, 2, 0, 0)
        github_row.setSpacing(6)
        github_row.addStretch(1)

        icon_size = description.fontMetrics().height()
        github_icon = QLabel()
        github_icon.setObjectName("AboutGitHubIcon")
        github_pixmap = self._themed_svg_pixmap(GITHUB_ICON_FILE, icon_size)
        github_icon.setPixmap(github_pixmap)
        github_icon.setFixedSize(icon_size, icon_size)
        github_row.addWidget(github_icon, 0, Qt.AlignmentFlag.AlignVCenter)

        github_url = self._t("dialog.github_url")
        link_color = self.palette().link().color().name()
        github_link = QLabel(
            f'<a href="{github_url}" style="color: {link_color};">{github_url}</a>'
        )
        github_link.setObjectName("AboutGitHubLink")
        github_link.setTextFormat(Qt.TextFormat.RichText)
        github_link.setOpenExternalLinks(True)
        github_link.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextBrowserInteraction
        )
        github_row.addWidget(github_link, 0, Qt.AlignmentFlag.AlignVCenter)
        github_row.addStretch(1)
        info.addLayout(github_row)

        layout.addLayout(info)

        project = QLabel(
            self._t("dialog.about_project", path=self._store.root)
        )
        project.setAlignment(Qt.AlignmentFlag.AlignCenter)
        project.setWordWrap(True)
        project.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        layout.addWidget(project)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok, dialog)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText(
            self._t("dialog.ok")
        )
        buttons.accepted.connect(dialog.accept)
        layout.addWidget(buttons, 0, Qt.AlignmentFlag.AlignHCenter)

        return dialog

    def _themed_svg_pixmap(self, path: Path, size: int) -> QPixmap:
        renderer = QSvgRenderer(str(path))
        if not renderer.isValid():
            return QPixmap()

        ratio = 2
        pixmap = QPixmap(size * ratio, size * ratio)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        renderer.render(painter)
        painter.setCompositionMode(
            QPainter.CompositionMode.CompositionMode_SourceIn
        )
        painter.fillRect(pixmap.rect(), self.palette().link().color())
        painter.end()
        pixmap.setDevicePixelRatio(ratio)
        return pixmap

    def _show_about(self) -> None:
        dialog = self._build_about_dialog()
        dialog.exec()

    def closeEvent(self, event: QCloseEvent) -> None:
        self._remember_scan_form()
        if self._runner.is_running:
            self._runner.kill()
        super().closeEvent(event)

    @staticmethod
    def _kind(item: QTreeWidgetItem) -> str:
        return str(item.data(0, KIND_ROLE) or "")
