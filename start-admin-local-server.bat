@echo off
setlocal

REM Starts the real SchoolDom backend and frontend for LAN CBT use.
REM Run this on the admin computer, then give students this computer's LAN IP.

cd /d "%~dp0"

start "SchoolDom Django API" cmd /k "venv\Scripts\python.exe manage.py runserver 0.0.0.0:8000"
start "SchoolDom Frontend" cmd /k "cd backend\frontend && set VITE_BACKEND_PROXY_TARGET=http://127.0.0.1:8000&& npm run dev -- --host 0.0.0.0"

echo.
echo SchoolDom local server is starting.
echo Admin dashboard: http://localhost:5173
echo Student CBT route: http://YOUR-LAN-IP:5173/student-cbt
echo.
pause
