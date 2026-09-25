$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$python = Join-Path $PSScriptRoot '.venv-release\Scripts\python.exe'
$compiler = Join-Path $PSScriptRoot '.inno-compiler\ISCC.exe'
if (!(Test-Path $python) -or !(Test-Path $compiler)) {
    throw 'Create .venv-release with requirements-release.txt and install Inno Setup in .inno-compiler first.'
}
Remove-Item Env:PYTHONPATH -ErrorAction SilentlyContinue
$icon = Join-Path $PSScriptRoot 'assets\icon.ico'
$assets = Join-Path $PSScriptRoot 'assets'
& $python -m PyInstaller --noconfirm --onedir --windowed --noupx --name TableTennisLive --distpath release\app --workpath release\build --specpath release --icon $icon --add-data "$assets;assets" main.py
if ($LASTEXITCODE -ne 0) { throw 'Application build failed' }
$report = Join-Path $PSScriptRoot ('release\self-test-' + [guid]::NewGuid().ToString() + '.json')
$app = Start-Process -FilePath '.\release\app\TableTennisLive\TableTennisLive.exe' -ArgumentList @('--self-test', ('"' + $report + '"')) -WindowStyle Hidden -PassThru
if (!$app.WaitForExit(20000)) { throw "Self-test timed out: $($app.Id)" }
if ($app.ExitCode -ne 0 -or !(Test-Path $report)) { throw 'Qt self-test failed' }
if (!(Get-Content -Raw $report | ConvertFrom-Json).ok) { throw 'UI verification failed' }
& $compiler installer.iss
if ($LASTEXITCODE -ne 0) { throw 'Installer build failed' }
