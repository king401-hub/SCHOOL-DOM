@echo off
setlocal

:: ── .NET Framework 4.0 prerequisite check ──────────────────────────────────
reg query "HKLM\SOFTWARE\Microsoft\NET Framework Setup\NDP\v4\Full" >nul 2>&1
if %errorlevel% equ 0 goto :dotnet_ok
reg query "HKLM\SOFTWARE\Microsoft\NET Framework Setup\NDP\v4\Client" >nul 2>&1
if %errorlevel% equ 0 goto :dotnet_ok

echo.
echo  ================================================================
echo   SchoolDom Student CBT requires .NET Framework 4.0 or later,
echo   which is NOT installed on this computer.
echo.
echo   Download it free from Microsoft:
echo   https://go.microsoft.com/fwlink/?LinkId=225702
echo.
echo   Install .NET Framework first, then run this setup again.
echo  ================================================================
echo.
pause
exit /b 1

:dotnet_ok
:: ── Windows Service Pack check ───────────────────────────────────────────────
for /f "tokens=3" %%v in ('reg query "HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion" /v "CurrentBuildNumber" 2^>nul') do set WINBUILD=%%v
if "%WINBUILD%"=="7600" (
    echo.
    echo  ================================================================
    echo   IMPORTANT: Your Windows 7 does not have Service Pack 1.
    echo.
    echo   Because .NET Framework 4.5 (required by this app) was
    echo   installed on this PC via Windows Update, it now requires
    echo   Windows 7 SP1 to run .NET applications.
    echo.
    echo   Please install Windows 7 Service Pack 1:
    echo   https://support.microsoft.com/kb/976932
    echo.
    echo   After installing SP1, run this setup again.
    echo  ================================================================
    echo.
    pause
    exit /b 1
)

:: ── Install ─────────────────────────────────────────────────────────────────
set APPDIR=%LOCALAPPDATA%\Programs\SchoolDom Student CBT Win7
if not exist "%APPDIR%" mkdir "%APPDIR%"
copy /Y "%~dp0SchoolDom.StudentCbt.Win7.exe"        "%APPDIR%\SchoolDom.StudentCbt.Win7.exe"        >nul
copy /Y "%~dp0SchoolDom.StudentCbt.Win7.exe.config" "%APPDIR%\SchoolDom.StudentCbt.Win7.exe.config" >nul
copy /Y "%~dp0README.txt"                            "%APPDIR%\README.txt"                            >nul
powershell -NoProfile -ExecutionPolicy Bypass -Command "$s=(New-Object -COM WScript.Shell).CreateShortcut([Environment]::GetFolderPath('Desktop') + '\SchoolDom Student CBT Win7.lnk'); $s.TargetPath=$env:LOCALAPPDATA + '\Programs\SchoolDom Student CBT Win7\SchoolDom.StudentCbt.Win7.exe'; $s.WorkingDirectory=$env:LOCALAPPDATA + '\Programs\SchoolDom Student CBT Win7'; $s.Save()"
start "" "%APPDIR%\SchoolDom.StudentCbt.Win7.exe"
endlocal
