# SchoolDom CBT Client

Professional offline-first Electron CBT desktop app for SchoolDom schools.

## What It Does

- Admin syncs published exams and students from the SchoolDom Django cloud before exam day, or keeps the already-synced package fully offline.
- Admin sets Wi-Fi, hotspot, or lab LAN details manually outside the app.
- Students sign in with Student ID and Exam PIN.
- Exams run offline with SQLite autosave every second.
- Student submissions are queued locally and pushed back to the cloud when internet returns.

## Main Folders

- `electron/main.cjs` - Electron window, secure IPC, fullscreen controls.
- `electron/preload.cjs` - safe renderer bridge.
- `electron/db.cjs` - encrypted SQLite storage, attempts, answers, sync queue, activity logs.
- `electron/syncService.cjs` - SchoolDom cloud sync and result upload.
- `src/App.jsx` - React screens for admin sync, student login, instructions, exam, summary, and status.
- `src/styles.css` - blue-and-white production UI.

## Backend Endpoints

The app uses:

- `GET /api/exams/cbt/offline-sync/`
- `POST /api/exams/cbt/offline-results/`
- `GET /api/exams/cbt/package/export/`
- `POST /api/exams/cbt/package/results/import/`

Both require a JWT from an admin/teacher-style SchoolDom account.

The desktop app does not start or require a local server. Once exams are synced into the local encrypted SQLite file, students can write directly on the desktop client without internet.

## Pull, Lock, Track, Push Lifecycle

1. **Pull** - Admin downloads or syncs `schooldom_cbt_exam_package` from the website.
2. **Lock** - The desktop app stores the active `package_id`, lock time, device ID, exams, and students in encrypted SQLite.
3. **Track** - Student sessions, answers, focus-loss events, submissions, and activity logs are written locally while offline.
4. **Push** - Results are uploaded as `schooldom_cbt_result_sync` envelopes containing the package ID, device ID, sync ID, checksum, answers, grades input, and audit logs. The website still accepts old raw result payloads for compatibility.

## No-Server Package Workflow

1. On a computer that can access SchoolDom, download `GET /api/exams/cbt/package/export/`.
2. Move the downloaded JSON file to the exam computer with a flash drive or shared folder.
3. In the CBT client, choose **Import Exam Package**.
4. Students write exams fully offline.
5. After the exam, choose **Export Results Package**.
6. Move the result JSON file back to a computer with SchoolDom access and upload it to `POST /api/exams/cbt/package/results/import/`.

## Development

```bash
npm install
npm run dev
```

The default SchoolDom cloud URL is `https://schooldom.academy`. Override it with `SCHOOLDOM_CLOUD_URL` only for testing another deployment.

## Packaging for Windows

```bash
npm run dist
```

The installer is written to `release/`.

To make the website download button serve the offline CBT client, copy the generated setup exe to:

```text
media/app/student-cbt/SchoolDomCBT.exe
```

## PIN Note

Existing Django exam PINs are stored hashed and cannot be recovered as plain text. During sync, enter the published exam PIN in the Admin Sync screen as the fallback offline PIN. Future backend PIN generation can expose a desktop-safe `offline_pin_hash` so the admin does not need to re-enter it.
