param(
    [string]$Configuration = "Release",
    [string]$Version = "0.1.0"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Solution = Join-Path $Root "SchoolDom.Cbt.Win7.sln"
$ProjectDir = Join-Path $Root "SchoolDom.Cbt.Win7"
$OutputDir = Join-Path $ProjectDir "bin\$Configuration"
$ReleaseDir = Join-Path $Root "release"
$ZipPath = Join-Path $ReleaseDir "SchoolDom-Admin-Sync-Win7-$Version.zip"

# Sync the compiled-in assembly version with the release version being built.
# Application.ProductVersion (the title bar text AND the auto-updater's "am I
# already on the latest version" comparison in Program.cs) reads this from
# AssemblyInfo.cs, NOT from -Version above (which only ever named the output
# zip/installer file) - leaving them out of sync is what made the app keep
# reporting an old version (and re-prompting to update forever) even after a
# successful install.
if ($Version -notmatch '^\d+(\.\d+){0,3}$') {
    throw "-Version must be numeric (e.g. 0.2.12), not '$Version'."
}
$asmVersion = "$Version.0"
$asmInfoPath = Join-Path $ProjectDir "Properties\AssemblyInfo.cs"
$asmInfoContent = Get-Content $asmInfoPath -Raw
# Matches whatever is currently inside the quotes, not just digits/dots - a regex that
# only matched an already-numeric string would silently no-op (and this script would
# still print "success") if a previous run ever left a bad/non-numeric value in place.
$asmInfoContent = $asmInfoContent -replace 'AssemblyVersion\("[^"]*"\)', "AssemblyVersion(`"$asmVersion`")"
$asmInfoContent = $asmInfoContent -replace 'AssemblyFileVersion\("[^"]*"\)', "AssemblyFileVersion(`"$asmVersion`")"
Set-Content -Path $asmInfoPath -Value $asmInfoContent -NoNewline -Encoding UTF8
$writtenContent = Get-Content $asmInfoPath -Raw
if ($writtenContent -notmatch [regex]::Escape("AssemblyVersion(`"$asmVersion`")") -or
    $writtenContent -notmatch [regex]::Escape("AssemblyFileVersion(`"$asmVersion`")")) {
    throw "Failed to write version $asmVersion into $asmInfoPath - check its AssemblyVersion/AssemblyFileVersion lines by hand."
}
Write-Host "Set assembly version to $asmVersion in $asmInfoPath"

# The bare v4.0.30319 MSBuild.exe (the last, always-present fallback below)
# ships a csc.exe that predates this project's LangVersion and fails with
# CS1617 on it. Real MSBuild from Visual Studio Build Tools 2019/2022 (the
# earlier candidates) doesn't have that problem - only fall back to a direct
# Roslyn compile (Invoke-RoslynFallbackBuild below) when nothing but the bare
# one was found.
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
        -ProjectFile (Join-Path $ProjectDir "SchoolDom.Cbt.Win7.csproj") `
        -OutputExePath (Join-Path $OutputDir "SchoolDom.Cbt.Win7.exe") `
        -Net40RuntimeDir $net40Runtime
}

$exe = Join-Path $OutputDir "SchoolDom.Cbt.Win7.exe"
if (!(Test-Path $exe)) {
    throw "Build output not found: $exe"
}

$packageDir = Join-Path $ReleaseDir "SchoolDom-Admin-Sync-Win7"
if (Test-Path $packageDir) {
    Remove-Item -Recurse -Force $packageDir
}
New-Item -ItemType Directory -Force -Path $packageDir | Out-Null
Copy-Item $exe (Join-Path $packageDir "SchoolDom.Cbt.Win7.exe")
Copy-Item (Join-Path $OutputDir "SchoolDom.Cbt.Win7.exe.config") (Join-Path $packageDir "SchoolDom.Cbt.Win7.exe.config")
Copy-Item (Join-Path $Root "README.md") (Join-Path $packageDir "README.txt")

$installCmd = Join-Path $packageDir "install.cmd"
@'
@echo off
setlocal
set APPDIR=%LOCALAPPDATA%\Programs\SchoolDom Admin Sync Win7
if not exist "%APPDIR%" mkdir "%APPDIR%"
copy /Y "%~dp0SchoolDom.Cbt.Win7.exe" "%APPDIR%\SchoolDom.Cbt.Win7.exe" >nul
copy /Y "%~dp0SchoolDom.Cbt.Win7.exe.config" "%APPDIR%\SchoolDom.Cbt.Win7.exe.config" >nul
copy /Y "%~dp0README.txt" "%APPDIR%\README.txt" >nul
powershell -NoProfile -ExecutionPolicy Bypass -Command "$s=(New-Object -COM WScript.Shell).CreateShortcut([Environment]::GetFolderPath('Desktop') + '\SchoolDom Admin Sync Win7.lnk'); $s.TargetPath=$env:LOCALAPPDATA + '\Programs\SchoolDom Admin Sync Win7\SchoolDom.Cbt.Win7.exe'; $s.WorkingDirectory=$env:LOCALAPPDATA + '\Programs\SchoolDom Admin Sync Win7'; $s.Save()"
start "" "%APPDIR%\SchoolDom.Cbt.Win7.exe"
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
    & $inno (Join-Path $Root "installer\SchoolDomCbtWin7.iss") "/DAppVersion=$Version"
    if ($LASTEXITCODE -ne 0) { Write-Warning "Inno Setup failed (exit $LASTEXITCODE) - ZIP is still available." }
}

Write-Host "Release package: $ZipPath"
