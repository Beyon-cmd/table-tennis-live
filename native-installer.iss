[Setup]
AppId={{AD0D067F-6750-48C3-8E61-593029EF05C1}
AppName=Table Tennis Live (WinUI)
AppVersion=2.0.0-preview.19
VersionInfoVersion=2.0.0.19
DefaultDirName={localappdata}\Programs\TableTennisLiveWinUI
DefaultGroupName=Table Tennis Live (WinUI)
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0.22000
OutputDir=release\native-winui-x64
OutputBaseFilename=TableTennisLive-WinUI-Preview19-Setup-x64
SetupIconFile=native\TableTennisLive.WinUI\Assets\AppIcon.ico
UninstallDisplayIcon={app}\TableTennisLive.WinUI.exe
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes

[Files]
Source: "release\native-winui-x64\app\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Tasks]
Name: desktopicon; Description: "创建桌面快捷方式"; Flags: checkedonce

[Icons]
Name: "{group}\Table Tennis Live (WinUI)"; Filename: "{app}\TableTennisLive.WinUI.exe"
Name: "{userdesktop}\Table Tennis Live (WinUI)"; Filename: "{app}\TableTennisLive.WinUI.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\TableTennisLive.WinUI.exe"; Description: "启动 Table Tennis Live"; Flags: nowait postinstall skipifsilent
