# SchoolDom CBT Win7 Client

Windows 7-compatible offline CBT client for SchoolDom.

This build targets `.NET Framework 4.8` and uses WinForms so it can run on
Windows 7 SP1 after the .NET Framework runtime is installed.

## Offline Package Workflow

1. Export a CBT package from SchoolDom:
   `/api/exams/cbt/package/export/`
2. Open this app as admin and choose **Import Package**.
3. Enter the exam PIN fallback if the exported package does not include
   `offline_pin_hash`.
4. Students sign in with Student ID and PIN.
5. Answers autosave locally.
6. Admin exports results as a JSON package.
7. Upload the package to SchoolDom:
   `/api/exams/cbt/package/results/import/`

## Cloud Workflow

Admin can also sync directly from the app:

1. Open **Admin**.
2. Choose **Cloud Login** or **Set Token**.
3. Choose **Pull From Cloud** to download published exams/students.
4. After exams are submitted, choose **Upload Results**.

If the admin account requires OTP, sign in through the website and paste the JWT
access token into **Set Token**. Direct cloud sync on Windows 7 requires SP1,
TLS 1.2 support, and updated root certificates. Keep offline package
import/export as the backup exam-day workflow.

## Exam Room Behavior

- Student screen uses Student ID + PIN.
- Exam mode switches to fullscreen borderless mode.
- Answers autosave locally every second.
- In-progress exams resume if the app/computer restarts.
- Closing the app during an exam requires confirmation and writes an audit log.
- Leaving the exam window increments the focus-loss counter.

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
release/SchoolDom-Student-CBT-Win7-0.1.0-Setup.exe
```

## Website Download

Copy the Win7 installer to:

```text
media/app/student-cbt/SchoolDomCBT-Win7.exe
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
