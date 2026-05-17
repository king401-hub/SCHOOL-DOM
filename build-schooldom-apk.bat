@echo off
setlocal

set "ROOT=%~dp0"
set "APP_DIR=%ROOT%mobile-app"
set "ANDROID_DIR=%APP_DIR%\android"
set "APK_SOURCE=%ANDROID_DIR%\app\build\outputs\apk\release\app-release.apk"
set "APK_TARGET=%ROOT%media\app\schooldom-app.apk"

if not exist "%APP_DIR%\node_modules" (
  echo Installing mobile app dependencies...
  pushd "%APP_DIR%"
  call npm install --legacy-peer-deps --no-audit --no-fund
  if errorlevel 1 exit /b 1
  popd
)

if not exist "%ANDROID_DIR%\gradlew.bat" (
  echo Generating Android native project...
  pushd "%APP_DIR%"
  call npx expo prebuild --platform android --no-install
  if errorlevel 1 exit /b 1
  popd
)

if not defined JAVA_HOME (
  if exist "C:\Program Files\Android\Android Studio\jbr\bin\java.exe" (
    set "JAVA_HOME=C:\Program Files\Android\Android Studio\jbr"
  )
)

if not exist "%JAVA_HOME%\bin\java.exe" (
  echo Java was not found. Install Android Studio or set JAVA_HOME to a JDK.
  exit /b 1
)

if not defined ANDROID_HOME (
  set "ANDROID_HOME=%LOCALAPPDATA%\Android\Sdk"
)
set "ANDROID_SDK_ROOT=%ANDROID_HOME%"

if not exist "%ANDROID_HOME%\platforms" (
  echo Android SDK was not found at "%ANDROID_HOME%".
  echo Open Android Studio ^> SDK Manager and install Android SDK Platform 34 and Build-Tools 34.0.0.
  exit /b 1
)

echo Building SchoolDom release APK...
pushd "%ANDROID_DIR%"
call gradlew.bat assembleRelease
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
