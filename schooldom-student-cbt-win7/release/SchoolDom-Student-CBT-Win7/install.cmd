@echo off
setlocal
rem %LOCALAPPDATA% does not exist on Windows XP ??? fall back to %APPDATA%
if defined LOCALAPPDATA (
    set APPDIR=%LOCALAPPDATA%\Programs\SchoolDom Student CBT Win7
) else (
    set APPDIR=%APPDATA%\SchoolDom Student CBT Win7
)
if not exist "%APPDIR%" mkdir "%APPDIR%"
copy /Y "%~dp0SchoolDom.StudentCbt.Win7.exe" "%APPDIR%\SchoolDom.StudentCbt.Win7.exe" >nul
copy /Y "%~dp0SchoolDom.StudentCbt.Win7.exe.config" "%APPDIR%\SchoolDom.StudentCbt.Win7.exe.config" >nul
copy /Y "%~dp0README.txt" "%APPDIR%\README.txt" >nul
rem Create desktop shortcut via VBScript ??? works on XP/Vista/7/10/11 without PowerShell
set VBS=%TEMP%\mkshortcut_%RANDOM%.vbs
echo Set oWS = WScript.CreateObject("WScript.Shell")                              > "%VBS%"
echo sLink = oWS.SpecialFolders("Desktop") ^& "\SchoolDom Student CBT Win7.lnk" >> "%VBS%"
echo Set oLink = oWS.CreateShortcut(sLink)                                       >> "%VBS%"
echo oLink.TargetPath = "%APPDIR%\SchoolDom.StudentCbt.Win7.exe"                 >> "%VBS%"
echo oLink.WorkingDirectory = "%APPDIR%"                                          >> "%VBS%"
echo oLink.Save                                                                   >> "%VBS%"
cscript //nologo "%VBS%"
del "%VBS%" >nul 2>&1
start "" "%APPDIR%\SchoolDom.StudentCbt.Win7.exe"
endlocal
