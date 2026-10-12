#define AppName "PSE Math"
[Setup]
AppId={{f384e6a9-0e68-4ae0-893c-0cde2e432fae}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=Andrej Ristic
AppPublisherURL=https://github.com/andrejristic/pse-math
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
LicenseFile={#SourceDir}\LICENSE.txt
OutputDir={#OutDir}
OutputBaseFilename=PSEMath-Setup-{#AppVersion}
SetupIconFile={#SourceDir}\pse-math.ico
UninstallDisplayIcon={app}\pse-math.exe
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\pse-math.exe"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\pse-math.exe"; Tasks: desktopicon
[Run]
Filename: "{app}\pse-math.exe"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent
