$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot

$project = Join-Path $PSScriptRoot 'native\TableTennisLive.WinUI\TableTennisLive.WinUI.csproj'
$compiler = Join-Path $PSScriptRoot '.inno-compiler\ISCC.exe'
$outputRoot = Join-Path $PSScriptRoot 'release\native-winui-x64'
$build = Join-Path $outputRoot 'build'
$app = Join-Path $outputRoot 'app'
$installer = Join-Path $outputRoot 'TableTennisLive-WinUI-Preview19-Setup-x64.exe'

if (!(Test-Path -LiteralPath $compiler)) {
    throw '未找到 Inno Setup 编译器：.inno-compiler\ISCC.exe'
}

dotnet publish $project -c Release -p:Platform=x64 -r win-x64 `
    -p:WindowsPackageType=None -p:WindowsAppSDKSelfContained=true `
    -p:SelfContained=true -p:PublishSingleFile=false `
    "-p:OutDir=$build\" -o $app
if ($LASTEXITCODE -ne 0) { throw 'WinUI 发布失败' }
if (!(Test-Path -LiteralPath (Join-Path $app 'TableTennisLive.WinUI.exe')) -or
    !(Test-Path -LiteralPath (Join-Path $app 'TableTennisLive.WinUI.pri')) -or
    !(Test-Path -LiteralPath (Join-Path $app 'Microsoft.WindowsAppRuntime.dll'))) {
    throw '发布目录缺少主程序、XAML 资源或 Windows App SDK 运行时'
}

& $compiler (Join-Path $PSScriptRoot 'native-installer.iss')
if ($LASTEXITCODE -ne 0 -or !(Test-Path -LiteralPath $installer)) {
    throw '安装包编译失败'
}
Get-Item -LiteralPath $installer | Select-Object FullName, Length, LastWriteTime
Get-FileHash -LiteralPath $installer -Algorithm SHA256
