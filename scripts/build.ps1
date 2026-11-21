param([switch]$Console, [switch]$Compat)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$python = Join-Path $root ".build-venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    $python = Join-Path $root ".venv\Scripts\python.exe"
}
if (-not (Test-Path $python)) {
    throw "未找到虚拟环境，请先运行 scripts\setup.ps1 -Dev"
}

& $python -c "import PyInstaller" 2>$null
if ($LASTEXITCODE -ne 0) {
    throw "未安装 PyInstaller，请先在当前虚拟环境安装 requirements-dev.txt"
}

$mode = if ($Console) { "--console" } else { "--windowed" }
$basePrefix = (& $python -c "import sys; print(sys.base_prefix)" | Out-String).Trim()
$libraryBin = Join-Path $basePrefix "Library\bin"

# Keep third-party toolchains on PATH from injecting incompatible DLLs into
# the bundle. In particular, Qt must load the Windows ICU libraries rather
# than an unrelated ICU build discovered in the shell environment.
$originalPath = $env:PATH
$originalCompatRoot = $env:RUSTSCAN_GUI_ROOT
$originalCompatConsole = $env:RUSTSCAN_GUI_CONSOLE
try {
    $searchPath = @()
    if (Test-Path $libraryBin) {
        $searchPath += $libraryBin
    }
    $searchPath += @("$env:SystemRoot\System32", $env:SystemRoot)
    $env:PATH = $searchPath -join ";"
    if ($Compat) {
        $env:RUSTSCAN_GUI_ROOT = $root
        $env:RUSTSCAN_GUI_CONSOLE = if ($Console) { "1" } else { "0" }
        & $python -m PyInstaller --noconfirm --clean `
            --distpath "$root\dist" --workpath "$root\build\pyinstaller-compat" `
            "$root\scripts\RustScan-GUI-compat.spec"
    }
    else {
        & $python -m PyInstaller --noconfirm --clean --onefile --noupx --name RustScan-GUI $mode `
            --icon "$root\assets\icons\rsg.ico" `
            --distpath "$root\dist" --workpath "$root\build\pyinstaller" `
            --specpath "$root\build" `
            --add-data "$root\assets;assets" --add-data "$root\language;language" `
            --add-binary "$root\bin\rustscan.exe;bin" "$root\main.py"
    }
    $exitCode = $LASTEXITCODE
}
finally {
    $env:PATH = $originalPath
    $env:RUSTSCAN_GUI_ROOT = $originalCompatRoot
    $env:RUSTSCAN_GUI_CONSOLE = $originalCompatConsole
}

exit $exitCode
