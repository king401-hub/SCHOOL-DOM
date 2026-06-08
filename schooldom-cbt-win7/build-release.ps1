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

$exe = Join-Path $OutputDir "SchoolDom.Cbt.Win7.exe"
if (!(Test-Path $exe)) {
    throw "Build output not found: $exe"
}

$packageDir = Join-Path $ReleaseDir "SchoolDom-Student-CBT-Win7"
if (Test-Path $packageDir) {
    Remove-Item -Recurse -Force $packageDir
}
New-Item -ItemType Directory -Force -Path $packageDir | Out-Null
Copy-Item $exe (Join-Path $packageDir "SchoolDom.Cbt.Win7.exe")
Copy-Item (Join-Path $Root "README.md") (Join-Path $packageDir "README.txt")

if (Test-Path $ZipPath) {
    Remove-Item -Force $ZipPath
}
Compress-Archive -Path (Join-Path $packageDir "*") -DestinationPath $ZipPath

$inno = "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe"
if (Test-Path $inno) {
    & $inno (Join-Path $Root "installer\SchoolDomCbtWin7.iss") "/DAppVersion=$Version"
}

Write-Host "Release package: $ZipPath"

