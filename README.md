<p align="center">
  <img src="assets/images/rsg-logo.png" alt="RustScan GUI" width="360" />
</p>

# RustScan-GUI

[English](README.md) | [简体中文](README_zh.md)

A GUI for RustScan built with **Python + PySide6 (Qt 6)**.

Features: **RustScan fast scanning, project-based scan management, importable address and port support for Sniper Scan and Pitchfork Scan, Nmap integration, script execution and management, and result viewing / CSV export**.

**All you love about Nmap is here can be continued here（Support Nmap）**

## Requirements

- Windows 10/11
- Python 3.10+ (the current development machine uses 3.14.7; if PySide6 installation fails, use 3.12/3.13)
- PySide6 (see `requirements.txt`)
- `bin/rustscan.exe` (RustScan 2.4.1, bundled)

## Quick Start

1. Run `dist\RustScan-GUI.exe` from the release build.

2. Alternatively, run from source:

```powershell
pip install -r requirements.txt
python main.py
```

## Project Data Layout

Projects and scans map directly to local folders. Renaming an item also renames or moves its folder:

```text
project/
├── New Project/
│   ├── New Scan/
│   │   └── result-2026-11-21-23-45-01.xml   # scan result
│   └── New Scan2/
└── New Project2/
    └── New Scan/
```

## Scan Page and XML Results

Select a scan in the left sidebar to open its detail page on the right:

- **Features**
  1. When both addresses and ports are imported from files, you can choose **Pitchfork Scan** or **Sniper Scan**.
     - **Sniper Scan**: every address is scanned against all imported ports. Manually entered ports use Sniper Scan by default.
     - **Pitchfork Scan**: addresses and imported ports are paired in one-to-one order.
  2. **Script management**: import Nmap scripts in `.nse` format.
  3. **Project management**: run scans for different projects and manage them inside the application.

- **Scan Options**
  - `* Scan address (supports domain, CIDR, and IP)`: the red asterisk marks a required field. A domain name, a single IP address, or a CIDR range is accepted.
  - `Import addresses from file (txt, csv)`: defaults to `No`. When set to `Yes`, the manual scan address input is disabled and you can enter or choose a `.txt` or `.csv` address file. TXT files accept one or more targets per line; CSV files read IP and domain columns using common English or Chinese headers. The switch and file path are saved in `scan_info.xml`.
  - If the imported address file also contains a port column, the application skips invalid address/port rows, switches the port mode to **File Import**, reuses the same file, and selects **Pitchfork Scan** automatically.
  - If the form is taller than the window, scroll with the mouse wheel. The **Start Scan** button stays fixed at the bottom of the page.
  - The port-mode dropdown offers `Port`, `Range`, and `File Import`.
  - With `Port` selected, the placeholder is `Ports (comma-separated, e.g. 80,8080)`.
  - With `Range` selected, the placeholder is `Range, e.g. (80-8080)`.
  - With `File Import` selected, use the **Choose** button to open a `.txt` or `.csv` port file. Ports must be between `0` and `65535`; invalid values are skipped.
  - When both the address and port sources are files, `Address and port scan type` becomes available. **Sniper Scan** scans every imported address against every imported port; **Pitchfork Scan** scans addresses and ports as one-to-one pairs.
  - A Pitchfork Scan runs paired jobs sequentially and writes one aggregated, timestamped XML result after all jobs finish.
  - `Add excluded IP addresses`: defaults to `No`. Select `Yes` to enter the IP addresses to exclude.
  - `Add excluded ports`: defaults to `No`. Select `Yes` to enter the ports to exclude.
  - `Ignore configuration file`: defaults to `No`.
  - `Use UDP mode`: defaults to `No`.
  - `Use Nmap service/version detection`: defaults to `No`. When set to `Yes`, `-g` is omitted and Nmap is invoked with `-sV` to identify service versions.
  - `Extra Nmap arguments`: always available. Enter additional Nmap arguments such as `-sC`; when provided, they are appended after `--` and passed to Nmap even when service/version detection is set to `No`.
  - `Use script`: defaults to `No`. Selecting `Yes` enables the script dropdown below it and lists the scripts available in the `script/` folder. During a scan, the absolute path of the selected script is passed to Nmap through `--script` and saved in `scan_info.xml`.
  - A light-blue `Start Scan` button is provided at the bottom of the page. The scan does not start when both the scan address and imported address file are empty.
  - Each scan folder receives a `scan_info.xml` file that stores the last-used scan options. The options are restored when the scan is selected again or the application is restarted.
- **Scan Results**
  - Reads every `.xml` result file in the current scan folder.
  - Each scan creates a timestamped result file named `result-YYYY-MM-DD-HH-MM-SS.xml`.
  - Multi-job scans such as Pitchfork store a language-neutral job count in the XML and render the target summary in the current interface language, for example `4 scan jobs` in English or `4 组扫描任务` in Simplified Chinese. Older result files using the previously localized target text are also recognized and translated.
  - The table shows address, port, protocol, state, service, and version.
  - A successful scan is written to the current scan folder automatically and the application switches to the result page. A failed scan does not overwrite existing results.
  - Both Nmap/RustScan `<nmaprun>` XML and the application's own result format are supported.
  - `scan_info.xml` is used only to store scan options and is never shown as a result file.
  - After adding a new XML file, click **Refresh** to load it again.
  - Use the green **Export as CSV** button to export every row from the currently selected result file. The CSV is saved with a UTF-8 BOM so it opens correctly in Excel.
- **Logs**
  - Located to the right of **Scan Results**. RustScan stdout/stderr is appended in real time.
  - Also records application state such as project/scan creation and renaming, language and theme changes, and scan start/completion/failure events.
  - Each line includes a timestamp and level (`INFO`, `SCAN`, `WARN`, `ERROR`) and automatically follows the latest entry.
  - Log entries are preserved when the interface language changes.

Example of the result format written by this application (see also `docs/sample_result.xml`):

```xml
<?xml version="1.0" encoding="utf-8"?>
<scan_results target="127.0.0.1" generated_at="2026-11-21T19:00:00+08:00">
  <result address="127.0.0.1" port="80" protocol="tcp" state="open" service="http" version="nginx 1.24.0"/>
</scan_results>
```

Multi-job results also include a `job_count` attribute, which the interface uses to localize the target summary without modifying the saved result file.

> Scans run asynchronously through `QProcess` and do not block the interface. RustScan runs in greppable mode; the application parses open ports and writes them to a timestamped `result-YYYY-MM-DD-HH-MM-SS.xml` file.

## Settings, Language, and Interface

- Open the settings page through `Edit → Settings` (`编辑 → 设置` in Simplified Chinese).
- Opening Settings closes the main project sidebar by default. The language navigation inside the settings page remains visible. Restore the main sidebar with `Ctrl+B` or `View → Show Sidebar`.
- The settings sidebar contains three pages: **Language**, **Interface**, and **Nmap Support**.
- The **Language** page offers `English` and `简体中文`.
- The **Interface** page provides **Display mode** with the options `Day` (light interface), `Night` (dark interface), and `Follow System`.
- Follow System reads the current light/dark appearance of the operating system and switches automatically when the system appearance changes.
- On first launch, the application creates `config.ini` in the program directory with `language = "en"` by default. The file is read on every subsequent launch.
- Changing the language immediately updates menus, the sidebar, scan options, result pages, dialogs, and the status bar, and rewrites `config.ini` with the selected language, for example `language = "zh_CN"`.
- Changing the display mode immediately updates the complete interface color scheme and writes the mode to `config.ini`, for example `display_mode = "light"`. If no display mode is configured, the dark theme is used.
- The **Nmap Support** page provides an **Nmap path** field. The default is `C:\Program Files (x86)\Nmap\nmap.exe`. Changes are written to `config.ini` and take effect for Nmap version detection and script scans.
- If `config.ini` is missing, invalid, or contains an unknown language code, the application falls back to English.
- `Edit → Main Interface` (`编辑 → 主界面` in Simplified Chinese, shortcut `Ctrl+1`) returns to the sidebar-and-workspace layout. If a scan is selected, the scan page is restored; otherwise the welcome page is shown.
- Switching languages preserves the selected scan and any values already entered in the scan form.
- Interface strings are stored in XML files under `language/`: `en.xml` and `zh_CN.xml`.
- Each XML node uses a stable `key` for an interface string, for example:

```xml
<language code="zh_CN" name="简体中文">
  <text key="menu.settings">设置</text>
  <text key="scan.start">开始扫描</text>
</language>
```

Example `config.ini`:

```ini
language = "en"
display_mode = "dark"
nmap_path = "C:\Program Files (x86)\Nmap\nmap.exe"
```

## Directory Structure

```text
RustScan-GUI/
├── main.py                     # application entry point
├── config.ini                  # language, display mode, and Nmap path (created on first launch)
├── bin/
│   └── rustscan.exe            # bundled RustScan executable
├── assets/
│   ├── icons/                  # folder, scan, and chevron icons (PNG)
│   ├── images/                 # image assets
│   └── styles/
│       ├── dark.qss            # dark theme stylesheet
│       └── light.qss           # light theme stylesheet
├── config/
│   └── settings.py             # constants, paths, and default configuration
├── language/
│   ├── en.xml                  # English interface strings
│   └── zh_CN.xml               # Simplified Chinese interface strings
├── core/                       # command construction, job planning, QProcess execution, output parsing
├── models/
│   ├── project.py              # project/scan node models
│   └── result.py               # port result model
├── services/
│   ├── project_store.py        # local folder creation, loading, and renaming
│   ├── address_file.py         # TXT/CSV address import and validation
│   ├── address_port_file.py    # address/port file pairing and invalid-row skipping
│   ├── port_file.py            # TXT/CSV port import for ports 0-65535
│   ├── scan_info_store.py      # scan_info.xml option persistence
│   ├── language_store.py       # XML language-pack loading and text lookup
│   ├── app_config.py           # config.ini language/display-mode/Nmap-path persistence
│   ├── script_store.py         # script/ listing, reading, creation, and deletion
│   └── result_store.py         # result XML save/load and Nmap XML parsing
├── ui/
│   ├── main_window.py          # menus, project tree, scan options/results pages
│   ├── widgets/                # custom widgets (planned)
│   └── dialogs/                # dialogs (planned)
├── utils/
│   ├── paths.py                # path resolution
│   ├── logger.py               # logging configuration
│   └── theme.py                # light/dark palettes and system-theme following
├── tests/                      # unit tests and offscreen UI tests
├── docs/                       # design notes and sample result XML
├── scripts/                    # environment, run, and build scripts
├── script/                     # user scripts (not tracked)
├── project/                    # user project data (generated at runtime, not tracked)
├── logs/                       # runtime logs (not tracked)
└── build/                      # build intermediates (not tracked)
```

## Current Features

- Top menu bar: **File / Edit / View / Scripts / Help** (**文件 / 编辑 / 视图 / 脚本 / 帮助** in Simplified Chinese).
- `Edit → Settings` opens the settings page. English and Simplified Chinese can be switched immediately; English is the default.
- `Settings → Interface → Display mode` supports Day, Night, and Follow System. Theme changes take effect immediately and are persisted.
- `Settings → Nmap Support` configures the Nmap executable path and persists it to `config.ini`.
- `Edit → Main Interface` returns to the sidebar and workspace; `Ctrl+1` is also available.
- `Scripts → Manage Scripts` opens the script-management page, listing scripts from `script/` on the left and showing the selected script on the right. Right-click a script to open it in Explorer or choose **Delete Script**; after confirmation, the local script file is removed and the scan script selector is refreshed.
- `Scripts → Add Script` opens a dialog. Enter a script name and content, then save with the green **Confirm** button.
- Language configuration is stored in `config.ini` in the program directory, read at startup, and updated when the language changes.
- `File → New Project`: creates a project folder under `project/` and adds a top-level item to the sidebar.
- `File → New Scan`: creates a scan subfolder inside the selected project. If no project is selected, the application prompts the user to select one first.
- Scan options support address and port files (TXT/CSV), automatic address/port pairing, and Sniper/Pitchfork scan modes.
- Duplicate names automatically receive a numeric suffix. Projects and scans can be renamed from their context menus.
- Renaming also moves the local folder. If the source folder is missing, it is recreated using the new name.
- The context menus for projects and scans provide **Delete**. The confirmation dialog offers the option to delete the corresponding local folder and files at the same time. When unchecked, the item is only hidden from the sidebar and local content is left untouched.
- Selecting a scan opens a three-tab page: **Scan Options / Scan Results / Logs**.
- The **Logs** tab on the right displays scan output and application state in real time.
- A light-blue **Start Scan** button at the bottom of Scan Options runs `bin/rustscan.exe` asynchronously.
- After a successful scan, the result is saved automatically to the current scan folder as `result-YYYY-MM-DD-HH-MM-SS.xml` and the result table is refreshed.
- Pitchfork and other multi-job results show the target count in the active interface language, so English and Chinese modes stay consistent after switching languages.
- Results are read from XML files in the local scan folder and displayed in a refreshable table.
- Context menus can open the corresponding directory in File Explorer.
- The sidebar can be closed with the `×` button in its upper-right corner or with `Ctrl+B`, and restored with `View → Show Sidebar`.
- Existing projects and scans under `project/` are loaded automatically at startup.
- Light, dark, and follow-system themes; environment status card; scrolling log (`logs/app.log`).

## Building the EXE

The build environment requires PySide6 and PyInstaller (run `scripts\setup.ps1 -Dev` first if needed). The build script prefers `.build-venv`, then falls back to `.venv`:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\build.ps1
```

The output is `dist\RustScan-GUI.exe`, a single-file program that contains Python, Qt, application resources, and the bundled RustScan executable. On first launch it creates `bin`, `language`, `logs`, `project`, `script`, and `config.ini` beside the EXE, and extracts the bundled `rustscan.exe` and language packs into their respective directories.

To build a compatibility edition for Windows 10/11 machines without a complete VC++ runtime or system ICU:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\build.ps1 -Compat
```

The compatibility build is written to `dist\RustScan-GUI-compat.exe`. It embeds Windows ICU and the complete 64-bit VC++ runtime.

To build a version with a console window for startup diagnostics:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\build.ps1 -Console
```

## Tests

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

The test suite covers project creation/deduplication/renaming, menu actions, script storage, creation, deletion, and the script-management page, the Add Script dialog and file writing, the settings page, Nmap path configuration and persistence, returning to the main interface, default English and Simplified Chinese switching, interface settings and all three display modes, follow-system repainting, reading/writing/fallback behavior for language, display mode, and Nmap path in `config.ini`, XML language-pack key integrity, sidebar toggling, mouse-wheel scrolling on the scan options page, real-time log output and preservation across language changes, scan page tabs, port-mode placeholders, Yes/No option defaults and linked fields, form-state preservation across language changes, TXT/CSV address and port import, invalid-row skipping, Sniper/Pitchfork planning, sequential multi-job scans, multi-job target localization, RustScan argument construction, output parsing, the start-scan workflow, and XML result save/load.

## Usage Notice

This repository and its artifacts are intended solely for authorized penetration testing.
