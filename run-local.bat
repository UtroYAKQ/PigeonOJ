@echo off
rem ============================================================
rem  PigeonOJ local one-click startup script for Windows
rem  - Starts PostgreSQL / MinIO / Redis infra containers (no pull)
rem  - Auto-installs missing backend (pip) / frontend (npm) dependencies
rem  - Builds the judge-node image only when missing (nsjail sandbox), runs 1 judge node in its own window
rem  - Runs DB migrations + demo user initialization
rem  - Starts the backend (port from .env SERVER_PORT, default 8000) and the frontend (5173)
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
echo [1/8] Checking Docker...
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

rem ---------- 2. Auto-install missing backend / frontend dependencies ----------
echo [2/8] Preparing dependencies...
cd /d "%~dp0src\backend"
python -c "import fastapi,uvicorn,alembic,sqlalchemy,redis,asyncpg,pydantic_settings,bcrypt,grpc,multipart,google.protobuf,ip2region,minio" >nul 2>&1
if errorlevel 1 (
    echo Backend python dependencies missing, running "pip install -r requirements.txt"...
    python -m pip install -r requirements.txt
    if errorlevel 1 ( echo [ERROR] Backend dependency install failed & pause & exit /b 1 )
) else (
    echo Backend python dependencies already installed
)
where npm >nul 2>&1
if errorlevel 1 (
    echo [ERROR] npm not found. Please install Node.js 18+ before running this script.
    pause
    exit /b 1
)
cd /d "%~dp0src\frontend"
if not exist "node_modules\" (
    echo Frontend node_modules missing, running "npm install"...
    call npm install
    if errorlevel 1 ( echo [ERROR] Frontend dependency install failed & pause & exit /b 1 )
) else (
    echo Frontend node_modules already present
)

rem ---------- 3. Prepare the judge-node image (pre-build the nsjail sandbox; first build takes time) ----------
echo [3/8] Preparing judge-node image...
docker image inspect pigeonoj/judge-node:latest >nul 2>&1
if errorlevel 1 (
    echo Judge-node image pigeonoj/judge-node not found, building...
    docker build -t pigeonoj/judge-node:latest "%~dp0src\judge"
    if errorlevel 1 ( echo [ERROR] Judge-node image build failed & pause & exit /b 1 )
) else (
    echo Judge-node image already exists
)

rem ---------- 4. Wait for PostgreSQL to be ready ----------
echo [4/8] Waiting for PostgreSQL to be ready...
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

rem ---------- 5. Migrate DB + init demo users + prepare backend ----------
echo [5/8] Running DB migration and demo user init...
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

rem ---------- 6. Start backend, wait for :50051 gateway (needed for judge node registration) ----------
echo [6/8] Starting backend...

rem Resolve the effective HTTP port through the real config chain
rem (process env > .env SERVER_PORT > backend.toml [server] port; fallback 8000),
rem then export SERVER_PORT so backend run.py and the frontend vite proxy share one value.
cd /d "%~dp0src\backend"
set "BE_PORT=8000"
for /f "delims=" %%p in ('python -c "from app.settings.config import get_settings; print(get_settings().server_port)" 2^>nul') do set "BE_PORT=%%p"
echo !BE_PORT!| findstr /r "^[0-9][0-9]*$" >nul 2>&1 || set "BE_PORT=8000"
set "SERVER_PORT=!BE_PORT!"
echo Backend port: !SERVER_PORT!

netstat -ano | findstr /c:":!SERVER_PORT! " | findstr /c:"LISTENING" >nul 2>&1
if errorlevel 1 (
    cd /d "%~dp0src\backend"
    start "PigeonOJ Backend" cmd /k "python run.py"
) else (
    echo [WARN] Port !SERVER_PORT! is occupied, backend may already be running; to restart, close the old window first
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
powershell -NoProfile -Command "try{Invoke-WebRequest -Uri 'http://127.0.0.1:!SERVER_PORT!/health' -UseBasicParsing -TimeoutSec 2|Out-Null;exit 0}catch{exit 1}" >nul 2>&1
if errorlevel 1 (
    timeout /t 1 /nobreak >nul
    goto wait_be
)
echo Backend is ready

rem ---------- 7. Start judge node in a dedicated window (copy .env.node.example to .env.node) ----------
echo [7/8] Starting judge node...
if not exist "%~dp0.env.node" copy /y "%~dp0.env.node.example" "%~dp0.env.node" >nul
rem Visible window: startup errors and node logs show there, so the node never needs a manual
rem "docker compose up" (which easily forgets --env-file .env.node).
rem No --build: reuse the image prepared in step 3; compose builds it only when the image is missing.
start "PigeonOJ Judge Node" cmd /k "docker compose --env-file %~dp0.env.node --project-directory %~dp0. -f %~dp0docker\docker-compose-node.yml up"

rem ---------- 8. Start frontend ----------
echo [8/8] Starting frontend...

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
echo   Backend:   http://127.0.0.1:!SERVER_PORT!  API docs at /docs
echo   Judge node: running in the "PigeonOJ Judge Node" window, gRPC registration at :50051
echo   Demo user:  admin@pigeonoj.dev / Admin@123
echo   Close the corresponding window to stop each service
echo ============================================
pause
