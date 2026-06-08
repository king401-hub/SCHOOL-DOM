# SchoolDom Admin Sync Win7

Windows 7-compatible admin sync client for SchoolDom.

This build targets `.NET Framework 4.8` and uses WinForms so it can run on
Windows 7 SP1 after the .NET Framework runtime is installed.

## Main Workflow

1. Open the app.
2. Cloud login is required on every launch.
3. After login, the app automatically pulls published exams, students, and CBT
   package metadata from SchoolDom.
4. Admin can refresh the local data with **Sync Now**.
5. Admin can upload/export any local result packages if needed.

## Cloud Sync

Admin can also sync directly from the app:

1. Open **Admin**.
2. Choose **Cloud Login** or **Set Token**.
3. Choose **Pull From Cloud** to download published exams/students.
4. After exams are submitted, choose **Upload Results**.

If the admin account requires OTP, sign in through the website and paste the JWT
access token into **Use JWT Token**. Direct cloud sync on Windows 7 requires SP1,
TLS 1.2 support, and updated root certificates.

## Admin-only Mode

The student exam writing screen has been removed. This app is now for:

- cloud login
- automatic school data pull
- local package inspection
- JSON package import/export recovery
- result upload/export when local result files exist

## Build

Open `SchoolDom.Cbt.Win7.sln` in Visual Studio or MSBuild with .NET Framework
4.8 developer tools installed, then build Release.

```powershell
msbuild SchoolDom.Cbt.Win7.sln /p:Configuration=Release
```

Or run:

```powershell
.\build-release.ps1 -Version 0.1.0
```

This writes a zip package to `release/`. If Inno Setup 6 is installed, it also
builds:

```text
release/SchoolDom-Admin-Sync-Win7-0.1.0-Setup.exe
```

## Website Download

Copy the Win7 installer to:

```text
media/app/student-cbt/SchoolDomAdminSync-Win7.exe
```

The backend exposes:

```text
/app/download/student-cbt/win7/
/app/download/student-cbt/win7/version/
```

The normal Windows 10/11 Electron CBT installer remains on:

```text
/app/download/student-cbt/
```

## Windows 7 Prerequisites

- Windows 7 Service Pack 1
- .NET Framework 4.8 runtime
- Current root certificates
- TLS 1.2 enabled for direct cloud sync

## Local Data

The app stores local exam data at:

```text
%APPDATA%\SchoolDom\CBTWin7\store.json
```
