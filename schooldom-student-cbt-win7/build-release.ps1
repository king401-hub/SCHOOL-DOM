param(
    [string]$Configuration = "Release",
    [string]$Version = "0.1.0"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Solution = Join-Path $Root "SchoolDom.StudentCbt.Win7.sln"
$ProjectDir = Join-Path $Root "SchoolDom.StudentCbt.Win7"
$OutputDir = Join-Path $ProjectDir "bin\$Configuration"
$ReleaseDir = Join-Path $Root "release"
$ZipPath = Join-Path $ReleaseDir "SchoolDom-Student-CBT-Win7-$Version.zip"

$msbuild = "$env:WINDIR\Microsoft.NET\Framework\v4.0.30319\MSBuild.exe"
if (!(Test-Path $msbuild)) {
    throw "MSBuild was not found at $msbuild. Install .NET Framework developer tools."
}

New-Item -ItemType Directory -Force -Path $ReleaseDir | Out-Null
& $msbuild $Solution /p:Configuration=$Configuration
if ($LASTEXITCODE -ne 0) {
    throw "Build failed."
}

$exe = Join-Path $OutputDir "SchoolDom.StudentCbt.Win7.exe"
if (!(Test-Path $exe)) {
    throw "Build output not found: $exe"
}

$packageDir = Join-Path $ReleaseDir "SchoolDom-Student-CBT-Win7"
if (Test-Path $packageDir) {
    Remove-Item -Recurse -Force $packageDir
}
New-Item -ItemType Directory -Force -Path $packageDir | Out-Null
Copy-Item $exe (Join-Path $packageDir "SchoolDom.StudentCbt.Win7.exe")
Copy-Item (Join-Path $OutputDir "SchoolDom.StudentCbt.Win7.exe.config") (Join-Path $packageDir "SchoolDom.StudentCbt.Win7.exe.config")

$readme = Join-Path $packageDir "README.txt"
@'
SchoolDom Student CBT Win7

Install this app on student computers. It does not use cloud login.
The admin computer must be on the same LAN and must have Admin LAN Starter running.
Students start exams with their Student ID and exam PIN.
'@ | Set-Content -Encoding ASCII $readme

$installCmd = Join-Path $packageDir "install.cmd"
@'
@echo off
setlocal
set APPDIR=%LOCALAPPDATA%\Programs\SchoolDom Student CBT Win7
if not exist "%APPDIR%" mkdir "%APPDIR%"
copy /Y "%~dp0SchoolDom.StudentCbt.Win7.exe" "%APPDIR%\SchoolDom.StudentCbt.Win7.exe" >nul
copy /Y "%~dp0SchoolDom.StudentCbt.Win7.exe.config" "%APPDIR%\SchoolDom.StudentCbt.Win7.exe.config" >nul
copy /Y "%~dp0README.txt" "%APPDIR%\README.txt" >nul
powershell -NoProfile -ExecutionPolicy Bypass -Command "$s=(New-Object -COM WScript.Shell).CreateShortcut([Environment]::GetFolderPath('Desktop') + '\SchoolDom Student CBT Win7.lnk'); $s.TargetPath=$env:LOCALAPPDATA + '\Programs\SchoolDom Student CBT Win7\SchoolDom.StudentCbt.Win7.exe'; $s.WorkingDirectory=$env:LOCALAPPDATA + '\Programs\SchoolDom Student CBT Win7'; $s.Save()"
start "" "%APPDIR%\SchoolDom.StudentCbt.Win7.exe"
endlocal
'@ | Set-Content -Encoding ASCII $installCmd

if (Test-Path $ZipPath) {
    Remove-Item -Force $ZipPath
}
Compress-Archive -Path (Join-Path $packageDir "*") -DestinationPath $ZipPath

$inno = "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe"
if (!(Test-Path $inno)) {
    $inno = Join-Path $env:LOCALAPPDATA "Programs\Inno Setup 6\ISCC.exe"
}
if (Test-Path $inno) {
    & $inno (Join-Path $Root "installer\SchoolDomStudentCbtWin7.iss") "/DAppVersion=$Version"
}

Write-Host "Release package: $ZipPath"
