@echo off
setlocal

set "ROOT=%~dp0"
set "APP_DIR=%ROOT%mobile-app-flutter"
set "APK_SOURCE=%APP_DIR%\build\app\outputs\flutter-apk\app-release.apk"
set "APK_TARGET=%ROOT%media\app\schooldom-app.apk"

if not exist "%APP_DIR%\pubspec.yaml" (
  echo Flutter project not found at "%APP_DIR%".
  exit /b 1
)

if not defined JAVA_HOME (
  if exist "C:\Program Files\Android\Android Studio\jbr\bin\java.exe" (
    set "JAVA_HOME=C:\Program Files\Android\Android Studio\jbr"
  )
)

if not defined ANDROID_HOME (
  set "ANDROID_HOME=%LOCALAPPDATA%\Android\Sdk"
)
set "ANDROID_SDK_ROOT=%ANDROID_HOME%"

if not exist "%ANDROID_HOME%\platforms" (
  echo Android SDK not found at "%ANDROID_HOME%".
  echo Open Android Studio ^> SDK Manager and install Android SDK Platform 35 and Build-Tools 35.0.0.
  exit /b 1
)

echo Getting Flutter packages...
pushd "%APP_DIR%"
call flutter pub get
if errorlevel 1 exit /b 1

echo Building SchoolDom release APK...
call flutter build apk --release
if errorlevel 1 exit /b 1
popd

if not exist "%APK_SOURCE%" (
  echo APK was not created at "%APK_SOURCE%".
  exit /b 1
)

if not exist "%ROOT%media\app" mkdir "%ROOT%media\app"
copy /Y "%APK_SOURCE%" "%APK_TARGET%"
if errorlevel 1 exit /b 1

echo.
echo Done. APK copied to:
echo %APK_TARGET%
echo.
echo Website download URL:
echo /app/download/apk/
