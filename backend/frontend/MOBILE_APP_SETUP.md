# SchoolDom App Setup

SchoolDom now supports two mobile paths from the same React frontend and Django backend:

- PWA install from the website landing page.
- Capacitor native wrapper using the built `dist` frontend.

## Website PWA

Run the normal frontend build:

```bash
npm run build
```

Deploy the generated `dist` output behind HTTPS. The landing page shows an install button when the browser supports PWA installation. On iPhone and iPad, Safari users can install through Share -> Add to Home Screen.

The service worker caches the app shell and static assets for fast loading and offline startup. Private API responses are not cached by the service worker.

## Shared Backend

The website can use relative API calls when the frontend and Django backend share a domain.

For Capacitor/native builds, set an absolute HTTPS backend URL before building:

```bash
VITE_API_BASE_URL=https://your-schooldom-domain.com
npm run build
npm run cap:sync
```

Both web and app users keep using the same Django backend, database, accounts, sessions, exams, attendance, messages, files, and finance records.

## Capacitor Wrapper

Install dependencies, build, and sync:

```bash
npm install
npm run build
npm run cap:sync
```

When native platforms are needed:

```bash
npx cap add android
npx cap add ios
npm run cap:sync
```

Android builds can be opened with:

```bash
npm run cap:open:android
```

iOS builds require macOS with Xcode:

```bash
npm run cap:open:ios
```
