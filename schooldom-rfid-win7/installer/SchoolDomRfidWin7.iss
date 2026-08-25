#define MyAppName "SchoolDom RFID Attendance"
#ifndef AppVersion
#define AppVersion "0.1.0"
#endif
#define MyAppPublisher "SchoolDom"
#define MyAppExeName "SchoolDom.Rfid.Win7.exe"

[Setup]
AppId={{C7EF2573-3FD7-4038-9073-BFA1D2B5B0A3}
AppName={#MyAppName}
AppVersion={#AppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\SchoolDom RFID Attendance
DefaultGroupName=SchoolDom RFID Attendance
DisableProgramGroupPage=yes
OutputDir=..\release
OutputBaseFilename=SchoolDom-Rfid-Win7-{#AppVersion}-Setup
SetupIconFile=..\SchoolDom.Rfid.Win7\Assets\schooldom.ico
Compression=lzma
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=
PrivilegesRequired=lowest
MinVersion=6.1

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "..\SchoolDom.Rfid.Win7\bin\Release\SchoolDom.Rfid.Win7.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\SchoolDom.Rfid.Win7\bin\Release\SchoolDom.Rfid.Win7.exe.config"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\SchoolDom RFID Attendance"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\SchoolDom RFID Attendance"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent
