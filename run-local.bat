@echo off
rem ============================================================
rem  PigeonOJ local one-click startup script for Windows
rem  - Starts PostgreSQL / MinIO / Redis infra containers (no pull)
rem  - Builds the judge-node image (with the nsjail sandbox) and runs 1 judge node by default
rem  - Runs DB migrations + demo user initialization
rem  - Starts the backend (8000) and the frontend (5173)
rem  Note: This script never executes user code; judging runs only inside the judge node's sandbox.
rem  Note: This is a batch file. Save it as ANSI/GBK (do NOT save as UTF-8).
rem ============================================================
setlocal enabledelayedexpansion
cd /d "%~dp0"
rem Python subprocesses (alembic / uvicorn / scripts) run in unified UTF-8 mode
rem to avoid UnicodeEncodeError on GBK consoles and locale/file-read errors.
set "PYTHONUTF8=1"

echo ============================================
echo   PigeonOJ local one-click startup
echo ============================================

rem ---------- 1. Check Docker ----------
echo [1/7] Checking Docker...
docker info >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Docker is not installed. Please install Docker Desktop before running this script.
    pause
    exit /b 1
)

rem ---------- PostgreSQL ----------
docker ps --format "{{.Names}}" | findstr /x "pigeonoj-postgres" >nul 2>&1
if errorlevel 1 (
    echo Starting PostgreSQL container...
    docker start pigeonoj-postgres >nul 2>&1
    if errorlevel 1 (
        docker run -d --name pigeonoj-postgres -e POSTGRES_USER=pigeonoj -e POSTGRES_PASSWORD=pigeonoj -e POSTGRES_DB=pigeonoj -p 5432:5432 -v pgdata:/var/lib/postgresql/data docker.1ms.run/postgres:16-alpine
    )
) else (
    echo PostgreSQL is already running
)

rem ---------- MinIO ----------
docker ps --format "{{.Names}}" | findstr /x "pigeonoj-minio" >nul 2>&1
if errorlevel 1 (
    echo Starting MinIO container...
    docker start pigeonoj-minio >nul 2>&1
    if errorlevel 1 (
        docker run -d --name pigeonoj-minio -e MINIO_ROOT_USER=pigeonoj -e MINIO_ROOT_PASSWORD=pigeonoj-minio-secret -p 9000:9000 -p 9001:9001 -v miniodata:/data docker.1ms.run/minio/minio:latest server /data --console-address ":9001"
    )
) else (
    echo MinIO is already running
)

rem ---------- Redis (only start if port 6379 is free) ----------
netstat -ano | findstr /c:":6379 " | findstr /c:"LISTENING" >nul 2>&1
if errorlevel 1 (
    docker ps --format "{{.Names}}" | findstr /x "pigeonoj-redis" >nul 2>&1
    if errorlevel 1 (
        echo Starting Redis container...
        docker start pigeonoj-redis >nul 2>&1
        if errorlevel 1 (
            docker run -d --name pigeonoj-redis -p 6379:6379 -v redisdata:/data docker.1ms.run/redis:7-alpine
        )
    ) else (
        echo Redis is already running
    )
) else (
    echo Redis is already running, port 6379 is occupied, reusing the existing instance
)

rem ---------- 2. Prepare the judge-node image (pre-build the nsjail sandbox; first build takes time) ----------
echo [2/7] Preparing judge-node image...
docker image inspect pigeonoj/judge-node:latest >nul 2>&1
if errorlevel 1 (
    echo Judge-node image pigeonoj/judge-node not found, building...
    docker build -t pigeonoj/judge-node:latest "%~dp0src\judge"
    if errorlevel 1 ( echo [ERROR] Judge-node image build failed & pause & exit /b 1 )
) else (
    echo Judge-node image already exists
)

rem ---------- 3. Wait for PostgreSQL to be ready ----------
echo [3/7] Waiting for PostgreSQL to be ready...
set /a attempts=0
:wait_db
set /a attempts+=1
if !attempts! gtr 30 (
    echo [ERROR] PostgreSQL not ready after 30 attempts, please check "docker ps"
    pause
    exit /b 1
)
powershell -NoProfile -Command "$c=New-Object Net.Sockets.TcpClient; try{$c.Connect('127.0.0.1',5432);$c.Close();exit 0}catch{exit 1}" >nul 2>&1
if errorlevel 1 (
    timeout /t 1 /nobreak >nul
    goto wait_db
)
echo PostgreSQL is ready

rem ---------- 4. Migrate DB + init demo users + prepare backend ----------
echo [4/7] Running DB migration and demo user init...
cd /d "%~dp0src\backend"
rem Variables set via "set K=V" so values carry into the started child consoles
rem (trailing spaces on values would break DB/MinIO connection strings, so no trailing spaces).
set "DATABASE_URL=postgresql+asyncpg://pigeonoj:pigeonoj@localhost:5432/pigeonoj"
set "REDIS_URL=redis://localhost:6379/0"
set "JUDGE_GATEWAY_TOKENS=dev-token"
python -m alembic upgrade head
if errorlevel 1 (
    echo [ERROR] DB migration failed, please check the log above
    pause
    exit /b 1
)
python -m scripts.bootstrap_demo_users

rem ---------- 5. Start backend, wait for :50051 gateway (needed for judge node registration) ----------
echo [5/7] Starting backend...

netstat -ano | findstr /c:":8000 " | findstr /c:"LISTENING" >nul 2>&1
if errorlevel 1 (
    cd /d "%~dp0src\backend"
    start "PigeonOJ Backend" cmd /k "python run.py"
) else (
    echo [WARN] Port 8000 is occupied, backend may already be running; to restart, close the old window first
)

rem Wait for the backend health endpoint (up to 30 tries) so the gRPC gateway is registered
rem and the judge node can register against it.
set /a hb=0
:wait_be
set /a hb+=1
if !hb! gtr 30 (
    echo [ERROR] Backend not ready after 30 attempts, please check the Backend startup log
    pause
    exit /b 1
)
powershell -NoProfile -Command "try{Invoke-WebRequest -Uri 'http://127.0.0.1:8000/health' -UseBasicParsing -TimeoutSec 2|Out-Null;exit 0}catch{exit 1}" >nul 2>&1
if errorlevel 1 (
    timeout /t 1 /nobreak >nul
    goto wait_be
)
echo Backend is ready

rem ---------- 6. Start judge node container (1 by default; copy .env.node.example to .env.node) ----------
echo [6/7] Starting judge node...
if not exist "%~dp0.env.node" copy /y "%~dp0.env.node.example" "%~dp0.env.node" >nul
docker compose --env-file "%~dp0.env.node" -f "%~dp0docker-compose-node.yml" up -d --build 1>nul 2>&1
if errorlevel 1 (
    echo [WARN] Judge node failed to start, please check .env.node and Docker logs; other services are unaffected, you can start it manually later
) else (
    start "PigeonOJ Judge Node" cmd /k "docker compose --env-file %~dp0.env.node -f %~dp0docker-compose-node.yml logs -f"
)

rem ---------- 7. Start frontend ----------
echo [7/7] Starting frontend...

netstat -ano | findstr /c:":5173 " | findstr /c:"LISTENING" >nul 2>&1
if errorlevel 1 (
    cd /d "%~dp0src\frontend"
    start "PigeonOJ Frontend" cmd /k "npm run dev"
) else (
    echo [WARN] Port 5173 is occupied, frontend may already be running
)

timeout /t 6 /nobreak >nul
start "" "http://localhost:5173"

echo.
echo ============================================
echo   Startup complete!
echo   Frontend:  http://localhost:5173
echo   Backend:   http://127.0.0.1:8000  API docs at /docs
echo   Judge node: Judge Node started, gRPC registration at :50051
echo   Demo user:  admin@pigeonoj.dev / Admin@123
echo   Close the corresponding window to stop each service
echo ============================================
pause
