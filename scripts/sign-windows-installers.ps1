[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$CertificatePath,

    [string]$CertificatePassword,

    [string]$AdminOutput = "media/app/admin/SchoolDomAdmin.exe",
    [string]$StudentOutput = "media/app/student-cbt/SchoolDomCBT.exe"
)

$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$cert = Resolve-Path $CertificatePath

if (-not $CertificatePassword) {
    $securePassword = Read-Host "Certificate password" -AsSecureString
    $credential = [System.Management.Automation.PSCredential]::new("code-signing", $securePassword)
    $CertificatePassword = $credential.GetNetworkCredential().Password
}

function Invoke-Step {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Name,

        [Parameter(Mandatory = $true)]
        [scriptblock]$Script
    )

    Write-Host ""
    Write-Host "==> $Name" -ForegroundColor Cyan
    & $Script
}

function Copy-Installer {
    param(
        [Parameter(Mandatory = $true)]
        [string]$SourcePattern,

        [Parameter(Mandatory = $true)]
        [string]$Destination
    )

    $installer = Get-ChildItem -Path $SourcePattern | Sort-Object LastWriteTime -Descending | Select-Object -First 1
    if (-not $installer) {
        throw "No installer found for pattern: $SourcePattern"
    }

    $target = Join-Path $repoRoot $Destination
    $targetDirectory = Split-Path $target -Parent
    New-Item -ItemType Directory -Force $targetDirectory | Out-Null
    Copy-Item -LiteralPath $installer.FullName -Destination $target -Force

    Write-Host "Copied signed installer to $Destination" -ForegroundColor Green
}

$env:CSC_LINK = $cert.Path
$env:CSC_KEY_PASSWORD = $CertificatePassword

Invoke-Step "Build Admin web assets" {
    Push-Location (Join-Path $repoRoot "schooldom-admin-app")
    try {
        npm.cmd run build
    }
    finally {
        Pop-Location
    }
}

Invoke-Step "Package and sign Admin installer" {
    Push-Location (Join-Path $repoRoot "schooldom-admin-app")
    try {
        npm.cmd run dist
    }
    finally {
        Pop-Location
    }
}

Copy-Installer `
    -SourcePattern (Join-Path $repoRoot "schooldom-admin-app/release/SchoolDom-Admin-*-Setup.exe") `
    -Destination $AdminOutput

Invoke-Step "Build Student CBT web assets" {
    Push-Location (Join-Path $repoRoot "schooldom-cbt-client")
    try {
        npm.cmd run build
    }
    finally {
        Pop-Location
    }
}

Invoke-Step "Package and sign Student CBT installer" {
    Push-Location (Join-Path $repoRoot "schooldom-cbt-client")
    try {
        .\node_modules\.bin\electron-builder.cmd
    }
    finally {
        Pop-Location
    }
}

Copy-Installer `
    -SourcePattern (Join-Path $repoRoot "schooldom-cbt-client/release/SchoolDom-Student-CBT-*-Setup.exe") `
    -Destination $StudentOutput

Remove-Item Env:\CSC_LINK -ErrorAction SilentlyContinue
Remove-Item Env:\CSC_KEY_PASSWORD -ErrorAction SilentlyContinue

Write-Host ""
Write-Host "Done. Both Windows installers were built with electron-builder signing enabled." -ForegroundColor Green
