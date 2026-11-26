@echo off
rem ============================================================
rem  PigeonOJ local one-click stop script for Windows
rem  Stops backend / frontend / judge node started by run-local.bat.
rem  Why this exists: closing a service window does not always kill
rem  the uvicorn reload worker (an orphaned child keeps holding the
rem  port), so stopping by port / compose is the reliable way.
rem  Note: This is a batch file. Save it as ANSI/GBK (do NOT save as UTF-8).
rem ============================================================
setlocal enabledelayedexpansion
cd /d "%~dp0"
set "PYTHONUTF8=1"

echo ============================================
echo   PigeonOJ local stop
echo ============================================

rem ---------- Backend (port from the real config chain, fallback 8000) ----------
set "BE_PORT=8000"
set "PY=%~dp0.venv\Scripts\python.exe"
if exist "%PY%" (
    for /f "delims=" %%p in ('"%PY%" -c "from app.settings.config import get_settings; print(get_settings().server_port)" 2^>nul') do set "BE_PORT=%%p"
)
echo !BE_PORT!| findstr /r "^[0-9][0-9]*$" >nul 2>&1 || set "BE_PORT=8000"
call :kill_port !BE_PORT!
echo Backend (port !BE_PORT!) stopped

rem ---------- Frontend (vite dev server) ----------
call :kill_port 5173
echo Frontend (port 5173) stopped

rem ---------- Judge node (docker compose project; containers only, image kept) ----------
if exist "%~dp0.env.node" (
    docker compose --env-file "%~dp0.env.node" --project-directory "%~dp0." -f "%~dp0docker\docker-compose-node.yml" down >nul 2>&1
    if not errorlevel 1 (
        echo Judge node containers stopped
    ) else (
        echo Judge node compose not running
    )
) else (
    echo Judge node .env.node missing, nothing to stop
)

echo.
echo All PigeonOJ local services stopped.
pause
exit /b 0

:kill_port
rem %1 = port; kill every LISTENING process on it (stale orphan from a closed window)
for /f "tokens=5" %%a in ('netstat -ano ^| findstr /c:":%1 " ^| findstr /c:"LISTENING"') do (
    echo [CLEANUP] Port %1: killing stale process PID %%a
    taskkill /F /PID %%a >nul 2>&1
)
exit /b 0
