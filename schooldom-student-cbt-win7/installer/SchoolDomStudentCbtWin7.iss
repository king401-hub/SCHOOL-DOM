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

[Code]
function IsDotNet40Installed(): Boolean;
var
  key: String;
  release: Cardinal;
begin
  key := 'SOFTWARE\Microsoft\NET Framework Setup\NDP\v4\Full';
  if RegQueryDWordValue(HKLM, key, 'Release', release) then
    Result := True
  else
    Result := RegKeyExists(HKLM, 'SOFTWARE\Microsoft\NET Framework Setup\NDP\v4\Client');
end;

function InitializeSetup(): Boolean;
begin
  if not IsDotNet40Installed() then
  begin
    MsgBox('.NET Framework 4.0 is required to run SchoolDom Student CBT.' + Chr(13) + Chr(10) +
           Chr(13) + Chr(10) +
           'Please download and install it from:' + Chr(13) + Chr(10) +
           'https://dotnet.microsoft.com/download/dotnet-framework/net40' + Chr(13) + Chr(10) +
           Chr(13) + Chr(10) +
           'After installing .NET 4.0, run this installer again.',
           mbError, MB_OK);
    Result := False;
  end
  else
    Result := True;
end;

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
