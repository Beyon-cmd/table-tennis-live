[Setup]
AppId={{1D4F74EC-4ABD-4BCB-AF59-EDC681D64A94}
AppName=Table Tennis Live
AppVersion=1.9.0
DefaultDirName={localappdata}\Programs\TableTennisLive
DefaultGroupName=Table Tennis Live
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0.17763
OutputDir=release
OutputBaseFilename=TableTennisLive-1.9.0-Setup-x64
SetupIconFile=assets\icon.ico
UninstallDisplayIcon={app}\TableTennisLive.exe
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes

[Files]
Source: "release\app\TableTennisLive\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Tasks]
Name: desktopicon; Description: "Create a desktop shortcut"; Flags: checkedonce

[Icons]
Name: "{group}\Table Tennis Live"; Filename: "{app}\TableTennisLive.exe"; IconFilename: "{app}\_internal\assets\icon.ico"
Name: "{userdesktop}\Table Tennis Live"; Filename: "{app}\TableTennisLive.exe"; IconFilename: "{app}\_internal\assets\icon.ico"; Tasks: desktopicon

[Run]
Filename: "{app}\TableTennisLive.exe"; Description: "Launch Table Tennis Live"; Flags: nowait postinstall skipifsilent
