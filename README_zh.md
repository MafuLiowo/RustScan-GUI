<p align="center">
  <img src="assets/images/rsg-logo.png" alt="RustScan GUI" width="360" />
</p>

# RustScan-GUI

[English](README.md) | [简体中文](README_zh.md)
**默认为英文版，需要在顶栏Edit/Settings/Language中更改为简体中文**

基于 **Python + PySide6（Qt 6）** 的 RustScan 图形GUI界面。

特色：**RustScan快速扫描、项目化扫描管理、可导入地址和端口的Sniper和Pitchfork扫描、可衔接Nmap版本扫描、脚本运行、脚本管理、结果查看与CSV导出**

**你所热爱的Nmap的使用习惯可以在这里延续（支持Nmap）**

## 环境要求

- Windows 10/11
- Python 3.10+（当前机器为 3.14.7；若 PySide6 安装失败，建议改用 3.12/3.13）
- PySide6（见 `requirements.txt`）
- `bin/rustscan.exe`（RustScan 2.4.1，已内置）

## 快速开始

1. 直接运行 `dist\RustScan-GUI.exe`

2.也可以手动执行：

```powershell
pip install -r requirements.txt
python main.py
```

## 项目数据布局

项目和扫描都直接映射到本机文件夹，重命名会同步移动文件夹：

```text
project/
├── New Project/
│   ├── New Scan/
│   │   └── result-2026-11-21-23-45-01.xml   # 扫描结果
│   └── New Scan2/
└── New Project2/
    └── New Scan/
```

## 扫描页面与 XML 结果

点击左侧栏中的扫描项，右侧会打开扫描详情页：

- **特色功能**
- 1.当从文件导入地址并从文件导入端口时，可以选择**Pitchfork扫描**以及**Sniper扫描**
-     Sniper扫描：每一个地址对应导入的所有的端口进行扫描（手动填入端口默认进行Sniper扫描）
-     Pitchfork扫描：地址与导入端口一一对应进行扫描
- 2.脚本管理：可导入nse格式的nmap脚本
- 3.项目管理：可以针对不同的项目进行扫描，在应用中管理项目

- **扫描选项**
  - `* 扫描地址（支持域名、CIDR、IP）`：红色星号表示必填，支持域名、单个 IP 或 CIDR 网段。
  - `从文件导入地址（支持txt、csv）`：默认 `否`；选择 `是` 后上方手动扫描地址输入框会变为不可输入，可填写或选择 `.txt`、`.csv` 地址文件。TXT 文件支持每行一个或多个目标；CSV 文件会自动匹配常见中英文表头中的 IP 或域名列。开关状态和文件路径都会保存在 `scan_info.xml` 中。
  - 如果导入的地址文件同时包含端口列，程序会自动跳过无效的地址及其对应端口，将端口模式切换为 `文件导入`，复用同一个文件，并自动选择 `Pitchfork扫描`。
  - 表单内容超出窗口高度时，可用鼠标滚轮上下滚动；“开始扫描”按钮固定在页面底部。
  - 端口模式下拉框可选 `端口`、`范围` 或 `文件导入`。
  - 选择 `端口` 时提示 `端口（逗号隔开，例如:80,8080）`。
  - 选择 `范围` 时提示 `范围，例如(80-8080)`。
  - 选择 `文件导入` 时，可点击右侧 `选择` 按钮打开 `.txt` 或 `.csv` 端口文件；端口范围为 `0-65535`，无效值会被跳过。
  - 当地址与端口都选择文件导入时，会显示 `地址与端口扫描类型`。`Sniper扫描` 会让每个导入地址都扫描全部导入端口；`Pitchfork扫描` 会把地址和端口按顺序一一对应扫描。
  - Pitchfork 扫描会依次执行每一组地址/端口任务，全部完成后写入一个带时间戳的汇总 XML 结果。
  - `是否添加排除IP地址`：默认 `否`；选择 `是` 后可填写排除的 IP 地址。
  - `是否添加排除端口`：默认 `否`；选择 `是` 后可填写排除端口。
  - `是否忽略配置文件`：默认 `否`。
  - `是否使用UDP模式`：默认 `否`。
  - `是否使用Nmap扫描版本信息`：默认 `否`；常规扫描统一使用 RustScan 的标准 `Open 主机:端口` 输出，不带 `-g`。选择 `是` 时调用 Nmap 并追加 `-sV` 识别服务版本。
  - `额外的Nmap扫描参数`：始终可输入，例如 `-sC`；填写后会追加到 `--` 之后传给 Nmap，即使“是否使用Nmap扫描版本信息”为 `否` 也会生效。
  - `是否使用脚本`：默认 `否`；选择 `是` 后会启用下方脚本下拉框，列出 `script/` 文件夹中的可用脚本。扫描时会把所选脚本的绝对路径通过 Nmap 的 `--script` 参数传入，并保存在 `scan_info.xml` 中。
  - 页面底部提供淡蓝色 `开始扫描` 按钮；扫描地址和导入地址文件都为空时不会启动。
  - 每个扫描文件夹会生成 `scan_info.xml`，保存上一次使用的扫描选项；重新选中该扫描或下次启动后会从文件恢复。
- **扫描结果**
  - 读取当前扫描文件夹内全部 `.xml` 结果文件。
  - 每次扫描都会生成带本地时间戳的结果文件，格式为 `result-YYYY-MM-DD-HH-MM-SS.xml`。
  - 日志中出现 `Open 主机:端口` 时，该开放端口会立即加入本次带时间戳的结果 XML 和当前结果表格；Nmap 服务和版本信息会在后续输出可用时补充。
  - Pitchfork 等由多个任务组成的扫描会把与语言无关的任务数量写入 XML，并根据当前界面语言显示目标摘要，例如英文下为 `4 scan jobs`，简体中文下为 `4 组扫描任务`。旧版本已保存为中文目标文本的结果文件也能正确识别并随界面语言切换。
  - 表格展示地址、端口、协议、状态、服务、版本。
  - 扫描成功后自动写入当前扫描文件夹，并切换到结果页；扫描失败不会覆盖已有结果。
  - 同时兼容 Nmap/RustScan 的 `<nmaprun>` XML 格式。
  - `scan_info.xml` 仅用于保存扫描选项，不会作为结果文件展示。
  - 放入新的 XML 后点击“刷新”即可重新读取。
  - 点击绿色“导出为CSV格式”按钮，可把当前选中的结果文件中的全部记录导出为 CSV；文件使用 UTF-8 BOM 编码，可直接用 Excel 打开。
- **日志**
  - 位于“扫描结果”右侧，实时追加 RustScan 的 stdout/stderr 输出。
  - 同时记录项目/扫描创建、重命名、语言与主题切换、扫描开始/完成/失败等程序状态。
  - 每行带时间与级别（`INFO`、`SCAN`、`WARN`、`ERROR`），并自动跟随最新日志。
  - 切换界面语言后日志内容会保留。

本应用写入的结果格式示例（也可参考 `docs/sample_result.xml`）：

```xml
<?xml version="1.0" encoding="utf-8"?>
<scan_results target="127.0.0.1" generated_at="2026-11-21T19:00:00+08:00">
  <result address="127.0.0.1" port="80" protocol="tcp" state="open" service="http" version="nginx 1.24.0"/>
</scan_results>
```

多任务结果还会包含 `job_count` 属性；界面会据此按当前语言显示目标摘要，无需修改已保存的结果文件。

> 扫描通过 `QProcess` 异步执行，不会阻塞界面。RustScan 输出 `Open 主机:端口` 行时，程序会立即解析并写入带时间戳的 `result-YYYY-MM-DD-HH-MM-SS.xml`。

## 设置、语言与界面

- 顶部 `Edit → Settings`（切换中文后为 `编辑 → 设置`）打开设置页。
- 打开设置页时会默认关闭主项目侧栏；设置页自身的语言导航仍保持显示，可用 `Ctrl+B` 或 `View → Show Sidebar` 恢复主侧栏。
- 设置页左侧提供“语言”、“界面”和“Nmap支持”三个导航项。
- “语言”页可选择 `English` 或 `简体中文`。
- “界面”页提供“显示模式”，可选 `Day / 日间`（浅色界面）、`Night / 夜间`（深色界面）和 `Follow System / 跟随系统`。
- 跟随系统会读取操作系统当前的浅色/深色外观，并在系统外观变化时自动切换。
- 应用首次启动时会在程序目录生成 `config.ini`，默认内容为 `language = "en"`；之后每次启动都会读取该文件。
- 切换语言后菜单、侧栏、扫描选项、结果页、提示框和状态栏立即更新，同时把 `config.ini` 改写为对应语言，例如 `language = "zh_CN"`。
- 切换显示模式后会立即更新整套界面配色，并把模式写入 `config.ini`，例如 `display_mode = "light"`。未设置显示模式时默认使用夜间主题。
- “Nmap支持”页提供“Nmap路径”输入框，默认值为 `C:\Program Files (x86)\Nmap\nmap.exe`；修改后会写入 `config.ini`，并在 Nmap 版本识别、脚本扫描时生效。
- `config.ini` 缺失、格式无效或语言代码不存在时回退英文。
- 顶部 `Edit → Main Interface`（简体中文为 `编辑 → 主界面`，快捷键 `Ctrl+1`）可随时返回“主侧栏 + 工作区”模式；若当前选中扫描则回到扫描页，否则回到欢迎页。
- 语言切换会保留当前选中的扫描和已填写的扫描选项。
- 界面文字存放在 `language/` 目录下的 XML 文件中：`en.xml`、`zh_CN.xml`。
- 每个 XML 节点使用稳定的 `key` 对应界面文字，例如：

```xml
<language code="zh_CN" name="简体中文">
  <text key="menu.settings">设置</text>
  <text key="scan.start">开始扫描</text>
</language>
```

`config.ini` 示例：

```ini
language = "en"
display_mode = "dark"
nmap_path = "C:\Program Files (x86)\Nmap\nmap.exe"
```

## 目录结构

```text
RustScan-GUI/
├── main.py                     # 程序入口
├── config.ini                  # 语言、显示模式与 Nmap 路径配置（首次启动生成）
├── bin/
│   └── rustscan.exe            # 内置 RustScan 可执行文件
├── assets/
│   ├── icons/                  # 文件夹、扫描、展开箭头图标（PNG）
│   ├── images/                 # 图片资源
│   └── styles/
│       ├── dark.qss            # 夜间主题样式
│       └── light.qss           # 日间主题样式
├── config/
│   └── settings.py             # 常量、路径与默认配置
├── language/
│   ├── en.xml                  # 英文界面文字
│   └── zh_CN.xml               # 简体中文界面文字
├── core/                       # 命令构建、任务规划、QProcess 扫描执行、输出解析
├── models/
│   ├── project.py              # 项目/扫描节点模型
│   └── result.py               # 端口结果模型
├── services/
│   ├── project_store.py        # 本地文件夹创建、加载与重命名
│   ├── address_file.py         # TXT/CSV 地址导入与校验
│   ├── address_port_file.py    # 地址/端口配对与无效行跳过
│   ├── port_file.py            # 0-65535 端口文件导入
│   ├── scan_info_store.py      # scan_info.xml 扫描选项持久化
│   ├── language_store.py       # XML 语言包加载与文本查询
│   ├── app_config.py           # config.ini 语言/显示模式/Nmap 路径读写
│   ├── script_store.py         # script/ 脚本列出、读取、添加与删除
│   └── result_store.py         # 结果 XML 保存、读取与 Nmap XML 解析
├── ui/
│   ├── main_window.py          # 菜单、项目树、扫描选项/结果页
│   ├── widgets/                # 自定义控件（待实现）
│   └── dialogs/                # 对话框（待实现）
├── utils/
│   ├── paths.py                # 路径解析
│   ├── logger.py               # 日志配置
│   └── theme.py                # 浅色/深色调色板与系统主题跟随
├── tests/                      # 单元测试与界面离屏测试
├── docs/                       # 设计与结果 XML 示例
├── scripts/                    # 环境与运行脚本
├── script/                     # 用户脚本（不纳入版本管理）
├── project/                    # 用户项目数据（运行后生成，不纳入版本管理）
├── logs/                       # 运行日志（不纳入版本管理）
└── build/                      # 打包输出（不纳入版本管理）
```

## 当前能力

- 顶部菜单栏：**File / Edit / View / Scripts / Help**（简体中文下为 **文件 / 编辑 / 视图 / 脚本 / 帮助**）。
- `编辑 → 设置` 打开设置页；支持 English 与简体中文即时切换，默认 English。
- `设置 → 界面 → 显示模式` 支持日间、夜间和跟随系统，主题切换立即生效并持久化。
- `设置 → Nmap支持` 可配置 Nmap 可执行文件路径，并持久化到 `config.ini`。
- `编辑 → 主界面` 返回侧栏与工作区，可通过 `Ctrl+1` 快速调用。
- `脚本 → 管理脚本` 打开脚本管理页，左侧列出 `script/` 中的脚本，右侧显示内容。右键脚本可“在资源管理器中打开”或“删除脚本”；确认删除后会同步移除本地脚本文件，并刷新扫描选项中的脚本下拉框。
- `脚本 → 添加脚本` 打开添加对话框，填写脚本名称与内容后使用绿色“确认”按钮保存。
- 语言配置保存在程序目录的 `config.ini`，启动时读取并在切换语言后同步更新。
- `文件 → 新建项目`：在 `project/` 下创建项目文件夹，并在左侧新增顶层项。
- `文件 → 新建扫描`：在选中项目内创建扫描子文件夹；未选中项目时会提示先选择。
- 扫描选项支持 TXT/CSV 地址与端口文件导入、地址端口自动配对，以及 Sniper/Pitchfork 两种扫描方式。
- 名称重复自动追加数字；项目与扫描名称均可在右键菜单中重命名。
- 重命名同步移动本机文件夹；源文件夹缺失时会按新名称补建。
- 项目与扫描的右键菜单提供“删除”；确认时可选择是否同时删除本地文件夹和文件。不勾选时仅从侧栏隐藏，本地内容保持不变。
- 点击扫描项显示“扫描选项 / 扫描结果 / 日志”三标签页面。
- 扫描页右侧提供“日志”标签，实时显示扫描输出和程序运行状态。
- 扫描选项页最下方提供淡蓝色“开始扫描”按钮，使用 `bin/rustscan.exe` 异步扫描。
- 扫描成功后结果自动保存到当前扫描文件夹的 `result-YYYY-MM-DD-HH-MM-SS.xml`，并刷新结果表格。
- Pitchfork 等多任务扫描的目标数量会按当前界面语言显示，切换中英文后结果摘要仍保持一致。
- 扫描结果从本机扫描文件夹的 XML 文件读取，支持表格展示与刷新。
- 右键菜单可在资源管理器中打开对应目录。
- 侧栏可通过右上角 `×` 或 `Ctrl+B` 关闭，使用 `视图 → 显示侧栏` 恢复。
- 启动时自动加载 `project/` 下已有项目和扫描。
- 日间/夜间/跟随系统主题、环境状态卡片、滚动日志（`logs/app.log`）。

## 打包为 EXE

构建环境需要安装 PySide6 与 PyInstaller（可先运行 `scripts\setup.ps1 -Dev`）。构建脚本优先使用 `.build-venv`，其次使用 `.venv`：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\build.ps1
```

输出文件为 `dist\RustScan-GUI.exe`，是包含 Python、Qt、资源文件与内置 RustScan 的单文件程序。首次运行会在 EXE 所在目录创建 `bin`、`language`、`logs`、`project`、`script` 和 `config.ini`，并将内置的 `rustscan.exe` 与语言包释放到对应目录。

如需在未安装完整 VC++ 运行库或系统 ICU 的 Windows 10/11 机器上运行，可构建兼容版：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\build.ps1 -Compat
```

兼容版输出为 `dist\RustScan-GUI-compat.exe`，会把 Windows ICU 与完整 64 位 VC++ 运行库一起内嵌。

如需带控制台窗口排查启动问题，可执行：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\build.ps1 -Console
```

## 测试

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

测试覆盖项目新建/去重/重命名、菜单动作、脚本存储、添加与删除、脚本管理页、添加脚本对话框与文件写入、设置页、Nmap 路径设置与持久化、主界面返回、默认英文与简体中文切换、界面设置与三种显示模式、跟随系统重绘、`config.ini` 语言/显示模式/Nmap 路径读写与无效配置回退、XML 语言包键值完整性、侧栏开关、扫描选项滚轮滚动、日志页实时输出与语言切换保留、扫描页标签、端口模式提示、是/否选项默认值与联动、语言切换后的表单状态保持、TXT/CSV 地址与端口导入、无效行跳过、Sniper/Pitchfork 扫描规划、多任务顺序扫描、多任务目标摘要语言适配、RustScan 参数构建、输出解析、开始扫描流程和 XML 结果保存/读取。

## 使用须知
本仓库及其产物仅用于授权的渗透测试行为
