param(
    [switch]$Dev,
    [string]$IndexUrl = "https://pypi.tuna.tsinghua.edu.cn/simple"
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    throw "未找到 python，请先安装 Python 3.10+ 并加入 PATH。"
}

if (-not (Test-Path ".venv")) {
    Write-Host "创建虚拟环境 .venv ..."
    python -m venv .venv
}

$python = Join-Path $root ".venv\Scripts\python.exe"
Write-Host "使用 PyPI 镜像: $IndexUrl"
& $python -m pip install --upgrade pip -i $IndexUrl --timeout 60
& $python -m pip install -r requirements.txt -i $IndexUrl --timeout 60

if ($Dev) {
    & $python -m pip install -r requirements-dev.txt -i $IndexUrl --timeout 60
}

Write-Host "环境已就绪。运行 scripts\run.ps1 启动应用。" -ForegroundColor Green