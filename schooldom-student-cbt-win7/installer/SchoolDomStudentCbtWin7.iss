#define MyAppName "SchoolDom Student CBT Win7"
#ifndef AppVersion
#define AppVersion "0.1.0"
#endif
#define MyAppPublisher "SchoolDom"
#define MyAppExeName "SchoolDom.StudentCbt.Win7.exe"

[Setup]
AppId={{8269D240-2322-48FD-9B46-2A6FB8C63F08}
AppName={#MyAppName}
AppVersion={#AppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\SchoolDom Student CBT Win7
DefaultGroupName=SchoolDom Student CBT Win7
DisableProgramGroupPage=yes
OutputDir=..\release
OutputBaseFilename=SchoolDom-Student-CBT-Win7-{#AppVersion}-Setup
SetupIconFile=..\SchoolDom.StudentCbt.Win7\Assets\schooldom.ico
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
Source: "..\SchoolDom.StudentCbt.Win7\bin\Release\SchoolDom.StudentCbt.Win7.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\SchoolDom.StudentCbt.Win7\bin\Release\SchoolDom.StudentCbt.Win7.exe.config"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\SchoolDom Student CBT Win7"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\SchoolDom Student CBT Win7"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent
