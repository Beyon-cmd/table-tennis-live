# 打包成不依赖 Python 的 Windows 单文件 exe
# 前置：python -m pip install -r requirements-build.txt
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $root

python -m PyInstaller --noconfirm --clean --onefile --windowed `
    --name TableTennisLive `
    --icon "assets\icon.ico" `
    --add-data "assets\icon.ico;assets" `
    "main.py"

Write-Host ""
Write-Host "完成：$root\dist\TableTennisLive.exe"
