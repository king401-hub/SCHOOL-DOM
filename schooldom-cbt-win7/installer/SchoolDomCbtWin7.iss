#define MyAppName "SchoolDom Admin Sync Win7"
#ifndef AppVersion
#define AppVersion "0.1.0"
#endif
#define MyAppPublisher "SchoolDom"
#define MyAppExeName "SchoolDom.Cbt.Win7.exe"

[Setup]
AppId={{D1C82680-29E7-47CF-80C6-B6561F861832}
AppName={#MyAppName}
AppVersion={#AppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\SchoolDom Admin Sync Win7
DefaultGroupName=SchoolDom Admin Sync Win7
DisableProgramGroupPage=yes
OutputDir=..\release
OutputBaseFilename=SchoolDom-Admin-Sync-Win7-{#AppVersion}-Setup
SetupIconFile=..\SchoolDom.Cbt.Win7\Assets\schooldom.ico
Compression=lzma
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=
PrivilegesRequired=lowest
MinVersion=6.1sp1

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "..\SchoolDom.Cbt.Win7\bin\Release\SchoolDom.Cbt.Win7.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\..\media\app\student-cbt\SchoolDomStudentCBT-Win7.exe"; DestDir: "{app}"; Flags: ignoreversion skipifsourcedoesntexist

[Icons]
Name: "{group}\SchoolDom Admin Sync Win7"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\SchoolDom Admin Sync Win7"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent
