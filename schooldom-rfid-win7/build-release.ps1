param(
    [string]$Configuration = "Release",
    [string]$Version = "0.1.0"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Solution = Join-Path $Root "SchoolDomRfidWin7.sln"
$ProjectDir = Join-Path $Root "SchoolDom.Rfid.Win7"
$OutputDir = Join-Path $ProjectDir "bin\$Configuration"
$ReleaseDir = Join-Path $Root "release"
$ZipPath = Join-Path $ReleaseDir "SchoolDom-Rfid-Win7-$Version.zip"

# Mirrors schooldom-cbt-win7/build-release.ps1 exactly (same reasoning: keep
# Application.ProductVersion, the compiled assembly version, and the release
# filename all in sync so an in-app "you're up to date" check can't lie).
if ($Version -notmatch '^\d+(\.\d+){0,3}$') {
    throw "-Version must be numeric (e.g. 0.1.0), not '$Version'."
}
$asmVersion = "$Version.0"
$asmInfoPath = Join-Path $ProjectDir "Properties\AssemblyInfo.cs"
$asmInfoContent = Get-Content $asmInfoPath -Raw
$asmInfoContent = $asmInfoContent -replace 'AssemblyVersion\("[^"]*"\)', "AssemblyVersion(`"$asmVersion`")"
$asmInfoContent = $asmInfoContent -replace 'AssemblyFileVersion\("[^"]*"\)', "AssemblyFileVersion(`"$asmVersion`")"
Set-Content -Path $asmInfoPath -Value $asmInfoContent -NoNewline -Encoding UTF8
$writtenContent = Get-Content $asmInfoPath -Raw
if ($writtenContent -notmatch [regex]::Escape("AssemblyVersion(`"$asmVersion`")") -or
    $writtenContent -notmatch [regex]::Escape("AssemblyFileVersion(`"$asmVersion`")")) {
    throw "Failed to write version $asmVersion into $asmInfoPath - check its AssemblyVersion/AssemblyFileVersion lines by hand."
}
Write-Host "Set assembly version to $asmVersion in $asmInfoPath"

$net40Runtime = "$env:WINDIR\Microsoft.NET\Framework\v4.0.30319"
$bareMsbuild = Join-Path $net40Runtime "MSBuild.exe"
$msbuildCandidates = @(
    "${env:ProgramFiles(x86)}\Microsoft Visual Studio\2022\BuildTools\MSBuild\Current\Bin\MSBuild.exe",
    "${env:ProgramFiles}\Microsoft Visual Studio\2022\BuildTools\MSBuild\Current\Bin\MSBuild.exe",
    "${env:ProgramFiles(x86)}\Microsoft Visual Studio\2022\Community\MSBuild\Current\Bin\MSBuild.exe",
    "${env:ProgramFiles}\Microsoft Visual Studio\2022\Community\MSBuild\Current\Bin\MSBuild.exe",
    "${env:ProgramFiles(x86)}\Microsoft Visual Studio\2019\BuildTools\MSBuild\Current\Bin\MSBuild.exe",
    "${env:ProgramFiles}\Microsoft Visual Studio\2019\BuildTools\MSBuild\Current\Bin\MSBuild.exe",
    $bareMsbuild
)
$msbuild = $msbuildCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if (!$msbuild) {
    throw "MSBuild was not found. Install Visual Studio Build Tools or .NET Framework developer tools."
}

New-Item -ItemType Directory -Force -Path $ReleaseDir | Out-Null

if ($msbuild -ne $bareMsbuild) {
    Write-Host "Using MSBuild: $msbuild"
    & $msbuild $Solution /p:Configuration=$Configuration "/p:FrameworkPathOverride=$net40Runtime\"
    if ($LASTEXITCODE -ne 0) {
        throw "Build failed."
    }
} else {
    . (Join-Path (Split-Path -Parent $Root) "RoslynFallbackBuild.ps1")
    Invoke-RoslynFallbackBuild `
        -ProjectFile (Join-Path $ProjectDir "SchoolDom.Rfid.Win7.csproj") `
        -OutputExePath (Join-Path $OutputDir "SchoolDom.Rfid.Win7.exe") `
        -Net40RuntimeDir $net40Runtime
}

$exe = Join-Path $OutputDir "SchoolDom.Rfid.Win7.exe"
if (!(Test-Path $exe)) {
    throw "Build output not found: $exe"
}

$packageDir = Join-Path $ReleaseDir "SchoolDom-Rfid-Win7"
if (Test-Path $packageDir) {
    Remove-Item -Recurse -Force $packageDir
}
New-Item -ItemType Directory -Force -Path $packageDir | Out-Null
Copy-Item $exe (Join-Path $packageDir "SchoolDom.Rfid.Win7.exe")
Copy-Item (Join-Path $OutputDir "SchoolDom.Rfid.Win7.exe.config") (Join-Path $packageDir "SchoolDom.Rfid.Win7.exe.config")

$installCmd = Join-Path $packageDir "install.cmd"
@'
@echo off
setlocal
set APPDIR=%LOCALAPPDATA%\Programs\SchoolDom RFID Attendance
if not exist "%APPDIR%" mkdir "%APPDIR%"
copy /Y "%~dp0SchoolDom.Rfid.Win7.exe" "%APPDIR%\SchoolDom.Rfid.Win7.exe" >nul
copy /Y "%~dp0SchoolDom.Rfid.Win7.exe.config" "%APPDIR%\SchoolDom.Rfid.Win7.exe.config" >nul
powershell -NoProfile -ExecutionPolicy Bypass -Command "$s=(New-Object -COM WScript.Shell).CreateShortcut([Environment]::GetFolderPath('Desktop') + '\SchoolDom RFID Attendance.lnk'); $s.TargetPath=$env:LOCALAPPDATA + '\Programs\SchoolDom RFID Attendance\SchoolDom.Rfid.Win7.exe'; $s.WorkingDirectory=$env:LOCALAPPDATA + '\Programs\SchoolDom RFID Attendance'; $s.Save()"
start "" "%APPDIR%\SchoolDom.Rfid.Win7.exe"
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
    & $inno (Join-Path $Root "installer\SchoolDomRfidWin7.iss") "/DAppVersion=$Version"
    if ($LASTEXITCODE -ne 0) { Write-Warning "Inno Setup failed (exit $LASTEXITCODE) - ZIP is still available." }
}

Write-Host "Release package: $ZipPath"
