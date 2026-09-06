@echo off
REM ============================================
REM  MedDoc Q&A - start backend + frontend
REM  Double-click this file, or run from terminal
REM ============================================
title MedDoc Q&A launcher

echo Starting MedDoc Q&A...
echo.

REM ---- backend ----
start "MedDoc backend (uvicorn :8000)" cmd /k "cd /d %~dp0backend && python -m uvicorn app.main:app --port 8000"

REM ---- frontend (installs deps first if missing) ----
if not exist "%~dp0frontend\node_modules" (
    start "MedDoc frontend (:5173)" cmd /k "cd /d %~dp0frontend && npm install && npm run dev"
) else (
    start "MedDoc frontend (:5173)" cmd /k "cd /d %~dp0frontend && npm run dev"
)

echo.
echo Two windows opened:
echo   Backend  : http://localhost:8000  (API docs at /docs)
echo   Frontend : http://localhost:5173  (open this in your browser)
echo.
echo Keep both windows open while using the app.
echo Close them (or press Ctrl+C inside each) to stop the servers.
pause
