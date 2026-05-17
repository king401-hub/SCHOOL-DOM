# SchoolDom App

This is the dedicated native mobile app for SchoolDom. It is separate from the React/Vite website and does not render the website inside a browser wrapper.

The app shares the same Django backend, APIs, authentication tokens, users, school database, messages, attendance, exams, files, and notifications.

See `../NATIVE_APP_ARCHITECTURE.md` for the full architecture notes.

## Run Locally

```bash
cd mobile-app
npm install
npm start
```

Set the backend URL before running against a hosted backend:

```bash
EXPO_PUBLIC_API_BASE_URL=https://your-schooldom-domain.com
npm start
```

For Android emulator local backend access, use `http://10.0.2.2:8000`.

## Native Builds

Without Android Studio, use Expo cloud build:

```bash
npx eas-cli login
npx eas-cli build --platform android --profile preview
```

When the build finishes, download the APK from the link Expo gives you and save it as:

```text
../media/app/schooldom-app.apk
```

For Play Store builds, use:

```bash
npx eas-cli build --platform android --profile production
```

Local native builds require Android Studio:

```bash
npm run prebuild
npm run android
npm run ios
```

iOS builds require macOS with Xcode.

## Architecture

- `src/api`: shared Django API client with JWT refresh.
- `src/auth`: session provider, biometric unlock, sign-in/sign-out.
- `src/navigation`: native stack and bottom-tab navigation.
- `src/screens`: dedicated mobile screens for dashboard, exams, messages, attendance, results, files, and settings.
- `src/services`: device services for push, GPS, camera, file picker, and background sync.
- `src/storage`: secure session storage, offline cache, and queued writes.
- `src/theme`: native UI tokens.
