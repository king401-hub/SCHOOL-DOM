# Shared by schooldom-student-cbt-win7/build-release.ps1 and
# schooldom-cbt-win7/build-release.ps1. Only used when this machine has no
# Visual Studio Build Tools installed, so the callers fell back to the bare
# .NET Framework v4.0.30319 MSBuild.exe - its bundled csc.exe predates
# LangVersion 6/7 and fails with CS1617 on these projects. Compiles directly
# with the newer Roslyn compiler bundled in any installed .NET SDK instead,
# driven entirely by what's actually declared in the .csproj (Compile items,
# Reference items, LangVersion, OutputType) so it can't drift out of sync
# with the project file over time.
function Invoke-RoslynFallbackBuild {
    param(
        [Parameter(Mandatory)] [string]$ProjectFile,
        [Parameter(Mandatory)] [string]$OutputExePath,
        [Parameter(Mandatory)] [string]$Net40RuntimeDir
    )

    $csc = Get-ChildItem -Path "$env:ProgramFiles\dotnet\sdk" -Filter "csc.dll" -Recurse -ErrorAction SilentlyContinue |
        Where-Object { $_.FullName -like "*\Roslyn\bincore\csc.dll" } |
        Sort-Object FullName -Descending |
        Select-Object -First 1
    if (!$csc) {
        throw "MSBuild here is too old to compile this project (it needs a newer LangVersion than the bare .NET Framework MSBuild supports), and no .NET SDK Roslyn compiler was found either to fall back to. Install the .NET SDK (https://dotnet.microsoft.com/download) or Visual Studio Build Tools 2019/2022 with the '.NET desktop development' workload, then re-run this script."
    }
    Write-Host "No Visual Studio Build Tools found - falling back to a direct Roslyn compile via: $($csc.FullName)"

    [xml]$proj = Get-Content $ProjectFile
    $projectDir = Split-Path -Parent $ProjectFile

    $sourceFiles = $proj.Project.ItemGroup.Compile |
        ForEach-Object { $_.Include } | Where-Object { $_ } |
        ForEach-Object { Join-Path $projectDir $_ }
    if (!$sourceFiles) { throw "No <Compile Include=...> entries found in $ProjectFile" }

    $refNames = $proj.Project.ItemGroup.Reference | ForEach-Object { $_.Include } | Where-Object { $_ }
    $langVersion = $proj.Project.PropertyGroup | ForEach-Object { $_.LangVersion } | Where-Object { $_ } | Select-Object -First 1
    if (!$langVersion) { $langVersion = "6" }
    $outputType = $proj.Project.PropertyGroup | ForEach-Object { $_.OutputType } | Where-Object { $_ } | Select-Object -First 1
    $targetKind = switch ($outputType) { "Library" { "library" }; "Exe" { "exe" }; default { "winexe" } }
    $appIcon = $proj.Project.PropertyGroup | ForEach-Object { $_.ApplicationIcon } | Where-Object { $_ } | Select-Object -First 1

    $refArgs = @("/r:$Net40RuntimeDir\mscorlib.dll")
    foreach ($name in $refNames) {
        $dll = Join-Path $Net40RuntimeDir "$name.dll"
        if (!(Test-Path $dll) -and $name -eq "WindowsBase") {
            $dll = Join-Path $Net40RuntimeDir "WPF\WindowsBase.dll"
        }
        if (Test-Path $dll) { $refArgs += "/r:$dll" }
        else { Write-Warning "Reference assembly not found, skipping: $name" }
    }

    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $OutputExePath) | Out-Null

    $cscArgs = @("/nologo", "/target:$targetKind", "/langversion:$langVersion", "/out:$OutputExePath")
    if ($appIcon) {
        $iconPath = Join-Path $projectDir $appIcon
        # MSBuild embeds <ApplicationIcon> as a real Win32 resource, which is what
        # Icon.ExtractAssociatedIcon(Application.ExecutablePath) reads at runtime for the
        # taskbar/title bar icon - without this the exe compiles fine but silently falls
        # back to Windows' generic exe icon everywhere.
        if (Test-Path $iconPath) { $cscArgs += "/win32icon:$iconPath" }
        else { Write-Warning "ApplicationIcon not found, skipping: $iconPath" }
    }
    $cscArgs += $refArgs + $sourceFiles
    & dotnet exec $csc.FullName @cscArgs
    if ($LASTEXITCODE -ne 0) { throw "Roslyn fallback compile failed." }

    # MSBuild would also emit <AssemblyName>.exe.config copied from App.config - replicate that.
    $appConfig = Join-Path $projectDir "App.config"
    if (Test-Path $appConfig) {
        Copy-Item $appConfig "$OutputExePath.config" -Force
    }
}
