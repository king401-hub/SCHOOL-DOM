# SchoolDom App Native Architecture

SchoolDom now has two separate client surfaces:

- `backend/frontend`: existing React/Vite website and installable PWA.
- `mobile-app`: dedicated React Native/Expo app with native screens and device services.

Both clients use the same Django backend, APIs, users, JWT authentication, tenant data, database records, messages, exams, attendance, finance, results, and notifications.

## Native App Principles

The native app is not a browser wrapper. It has its own:

- Native stack and bottom-tab navigation.
- Mobile login and OTP flow.
- Secure token storage through `expo-secure-store`.
- Optional biometric unlock through `expo-local-authentication`.
- Dashboard, exams, messages, attendance, results, and settings screens.
- Offline cache and queued writes for network loss.
- Background sync task for queued writes.
- GPS attendance support.
- Camera and file picker service layer.
- Push notification registration and foreground notification handling.

## Backend Additions

The backend now exposes:

```text
POST   /api/app/mobile/device/
DELETE /api/app/mobile/device/
```

This endpoint stores the native push token on the authenticated `User.device_tokens` field and mirrors it into notification preferences when available.

## Run The Native App

```bash
cd mobile-app
npm install
npm start
```

Set the backend URL:

```bash
EXPO_PUBLIC_API_BASE_URL=https://your-schooldom-domain.com
npm start
```

For Android emulator to reach a Django backend running on your computer:

```bash
EXPO_PUBLIC_API_BASE_URL=http://10.0.2.2:8000
npm start
```

For a physical phone, use your computer LAN IP or a public HTTPS URL.

## Build Android/iOS

Without Android Studio, use Expo cloud build from `mobile-app`:

```bash
npx eas-cli login
npx eas-cli build --platform android --profile preview
```

That produces a downloadable APK. Download it and save it as:

```text
media/app/schooldom-app.apk
```

Before building for real users, update `mobile-app/eas.json` and replace:

```text
https://your-schooldom-domain.com
```

with your live SchoolDom backend URL.

For Google Play Store upload, build an AAB:

```bash
npx eas-cli build --platform android --profile production
```

Local builds require Android Studio:

```bash
cd mobile-app
npm run prebuild
npm run android
npm run ios
```

iOS builds require macOS and Xcode.

## Website APK Download

The website download button points to:

```text
/app/download/
```

The direct APK endpoint is:

```text
/app/download/apk/
```

After building a release APK, upload or copy it to:

```text
media/app/schooldom-app.apk
```

On the VPS, the file path will be inside your deployed project folder, for example:

```bash
/path/to/virtual-school-platform/media/app/schooldom-app.apk
```

Until that file exists, the download page will show that the APK has not been uploaded yet.

On Windows, this repo includes a helper:

```bat
build-schooldom-apk.bat
```

It builds `mobile-app/android/app/build/outputs/apk/release/app-release.apk` and copies it to `media/app/schooldom-app.apk`. It requires Java plus the Android SDK platform/build-tools to be installed through Android Studio.

## Notes

The current implementation establishes the native app foundation and core role-aware screens. More complex web-only workflows can now be ported screen by screen into native components without changing the Django backend contract.
