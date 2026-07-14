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

$msbuildCandidates = @(
    "${env:ProgramFiles(x86)}\Microsoft Visual Studio\2022\BuildTools\MSBuild\Current\Bin\MSBuild.exe",
    "${env:ProgramFiles}\Microsoft Visual Studio\2022\BuildTools\MSBuild\Current\Bin\MSBuild.exe",
    "${env:ProgramFiles(x86)}\Microsoft Visual Studio\2022\Community\MSBuild\Current\Bin\MSBuild.exe",
    "${env:ProgramFiles}\Microsoft Visual Studio\2022\Community\MSBuild\Current\Bin\MSBuild.exe",
    "${env:ProgramFiles(x86)}\Microsoft Visual Studio\2019\BuildTools\MSBuild\Current\Bin\MSBuild.exe",
    "${env:ProgramFiles}\Microsoft Visual Studio\2019\BuildTools\MSBuild\Current\Bin\MSBuild.exe",
    "$env:WINDIR\Microsoft.NET\Framework\v4.0.30319\MSBuild.exe"
)
$msbuild = $msbuildCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if (!$msbuild) {
    throw "MSBuild was not found. Install Visual Studio Build Tools or .NET Framework developer tools."
}
Write-Host "Using MSBuild: $msbuild"
$net40Runtime = "$env:WINDIR\Microsoft.NET\Framework\v4.0.30319"

New-Item -ItemType Directory -Force -Path $ReleaseDir | Out-Null
& $msbuild $Solution /p:Configuration=$Configuration "/p:FrameworkPathOverride=$net40Runtime\"
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
    if ($LASTEXITCODE -ne 0) { Write-Warning "Inno Setup failed (exit $LASTEXITCODE) - ZIP is still available." }
}

Write-Host "Release package: $ZipPath"
