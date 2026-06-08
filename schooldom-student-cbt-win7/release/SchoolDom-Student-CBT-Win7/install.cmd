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
