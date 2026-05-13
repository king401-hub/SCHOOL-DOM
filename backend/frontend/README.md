# SchoolDom Frontend

This folder contains a standalone React auth page (sign in + sign up) that talks to the Django backend API.

## Run

```bash
npm install
npm run dev
```

Open the dev URL shown by Vite (default: `http://localhost:5173`).

## Current auth mode

- Uses backend endpoints:
  - `POST /api/auth/login/`
  - `POST /api/auth/register/`
  - `POST /api/auth/create-school/`
  - `GET /api/app/dashboard/`
  - `GET /api/app/students/`
  - `GET /api/app/teachers/`
  - `GET /api/app/enrollments/`
  - `GET /api/app/classes/`
  - `GET /api/app/exams/`
  - `GET /api/app/messages/`
  - `POST /api/app/teachers/create/`
  - `POST /api/app/enrollments/create/`
  - `POST /api/app/classes/create/`, `PATCH/DELETE /api/app/classes/{id}/`
  - `POST /api/app/exams/create/`, `PATCH/DELETE /api/app/exams/{id}/`
  - `GET /api/app/messages/inbox/`, `POST /api/app/messages/send/`
- Stores session in `localStorage` or `sessionStorage`.
- API base URL defaults to `http://127.0.0.1:8000` and can be overridden with `VITE_API_BASE_URL`.
- Includes a protected app shell with starter screens:
  - `/dashboard`
  - `/students`
  - `/teachers`
  - `/enrollments`
  - `/classes`
  - `/exams`
  - `/messages`
  - `/settings`

## Profile photo upload support

- `POST /api/app/teachers/create/` accepts optional multipart field: `profile_picture`.
- `POST /api/app/enrollments/create/` accepts optional multipart field: `profile_picture` for student creation (or existing student update in enrollment flow).
- Frontend automatically sends `FormData` when a photo is selected in teacher/student create forms.
