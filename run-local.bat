@echo off
rem ============================================================
rem  PigeonOJ 开发环境一键启动（Windows）
rem  - 启动 PostgreSQL / MinIO / Redis（本地镜像，不拉取）
rem  - 构建判题节点镜像（含 nsjail 沙箱层）并启动 1 个本地节点
rem  - 执行数据库迁移 + 引导演示账号
rem  - 启动后端 (8000) 与前端 (5173)
rem  说明：后端进程不执行用户代码；代码执行只发生在判题节点容器内。
rem  注意：本文件含中文，必须以 ANSI/GBK 编码保存（勿存为 UTF-8）。
rem ============================================================
setlocal enabledelayedexpansion
cd /d "%~dp0"
rem Python 子进程（alembic / uvicorn / 脚本）统一 UTF-8 模式，
rem 避免中文日志在 GBK 控制台触发 UnicodeEncodeError，以及 locale 编码读文件报错
set "PYTHONUTF8=1"

echo ============================================
echo   PigeonOJ 开发环境一键启动
echo ============================================

rem ---------- 1. 检查 Docker ----------
echo [1/7] 检查 Docker...
docker info >nul 2>&1
if errorlevel 1 (
    echo [错误] Docker 未运行，请先启动 Docker Desktop 再执行本脚本。
    pause
    exit /b 1
)

rem ---------- PostgreSQL ----------
docker ps --format "{{.Names}}" | findstr /x "pigeonoj-postgres" >nul 2>&1
if errorlevel 1 (
    echo 启动 PostgreSQL（本地镜像）...
    docker start pigeonoj-postgres >nul 2>&1
    if errorlevel 1 (
        docker run -d --name pigeonoj-postgres -e POSTGRES_USER=pigeonoj -e POSTGRES_PASSWORD=pigeonoj -e POSTGRES_DB=pigeonoj -p 5432:5432 -v pgdata:/var/lib/postgresql/data docker.1ms.run/postgres:16-alpine
    )
) else (
    echo PostgreSQL 已在运行
)

rem ---------- MinIO ----------
docker ps --format "{{.Names}}" | findstr /x "pigeonoj-minio" >nul 2>&1
if errorlevel 1 (
    echo 启动 MinIO（本地镜像）...
    docker start pigeonoj-minio >nul 2>&1
    if errorlevel 1 (
        docker run -d --name pigeonoj-minio -e MINIO_ROOT_USER=pigeonoj -e MINIO_ROOT_PASSWORD=pigeonoj-minio-secret -p 9000:9000 -p 9001:9001 -v miniodata:/data docker.1ms.run/minio/minio:latest server /data --console-address ":9001"
    )
) else (
    echo MinIO 已在运行
)

rem ---------- Redis（6379 未被占用时才启动） ----------
netstat -ano | findstr /c:":6379 " | findstr /c:"LISTENING" >nul 2>&1
if errorlevel 1 (
    docker ps --format "{{.Names}}" | findstr /x "pigeonoj-redis" >nul 2>&1
    if errorlevel 1 (
        echo 启动 Redis（本地镜像）...
        docker start pigeonoj-redis >nul 2>&1
        if errorlevel 1 (
            docker run -d --name pigeonoj-redis -p 6379:6379 -v redisdata:/data docker.1ms.run/redis:7-alpine
        )
    ) else (
        echo Redis 已在运行
    )
) else (
    echo Redis 已在运行（端口 6379 已被占用，复用现有实例）
)

rem ---------- 2. 构建判题节点镜像（含 nsjail 沙箱基础层；仅首次或 Dockerfile 变更时） ----------
echo [2/7] 准备判题节点镜像...
docker image inspect sandbox:local >nul 2>&1
if errorlevel 1 (
    echo 构建沙箱基础层 sandbox:local（仅首次，需几分钟）...
    docker build -t sandbox:local "%~dp0src\judge\sandbox"
    if errorlevel 1 ( echo [错误] 基础层构建失败 & pause & exit /b 1 )
)
docker image inspect pigeonoj/judge-node:latest >nul 2>&1
if errorlevel 1 (
    echo 构建判题节点镜像 pigeonoj/judge-node...
    docker build -t pigeonoj/judge-node:latest "%~dp0src\judge"
    if errorlevel 1 ( echo [错误] 节点镜像构建失败 & pause & exit /b 1 )
) else (
    echo 判题节点镜像已存在
)

rem ---------- 3. 等待 PostgreSQL 就绪 ----------
echo [3/7] 等待 PostgreSQL 就绪...
set /a attempts=0
:wait_db
set /a attempts+=1
if !attempts! gtr 30 (
    echo [错误] PostgreSQL 30 秒内未就绪，请检查 docker ps。
    pause
    exit /b 1
)
powershell -NoProfile -Command "$c=New-Object Net.Sockets.TcpClient; try{$c.Connect('127.0.0.1',5432);$c.Close();exit 0}catch{exit 1}" >nul 2>&1
if errorlevel 1 (
    timeout /t 1 /nobreak >nul
    goto wait_db
)
echo PostgreSQL 就绪

rem ---------- 4. 迁移 + 演示账号 + 公共环境变量 ----------
echo [4/7] 数据库迁移与演示账号引导...
cd /d "%~dp0src\backend"
rem 以下变量由本脚本统一 set，随后 start 的子窗口自动继承；
rem 必须用 set "K=V" 引号形式，避免值尾部混入空格（曾导致路径带尾空格判题失败）
set "DATABASE_URL=postgresql+asyncpg://pigeonoj:pigeonoj@localhost:5432/pigeonoj"
set "REDIS_URL=redis://localhost:6379/0"
set "JUDGE_GATEWAY_TOKENS=dev-token"
python -m alembic upgrade head
if errorlevel 1 (
    echo [错误] 数据库迁移失败，请检查上方日志。
    pause
    exit /b 1
)
python -m scripts.bootstrap_demo_users

rem ---------- 5. 启动后端（判题网关 :50051 随应用启动；须先于判题节点就绪） ----------
echo [5/7] 启动后端...

netstat -ano | findstr /c:":8000 " | findstr /c:"LISTENING" >nul 2>&1
if errorlevel 1 (
    cd /d "%~dp0src\backend"
    start "PigeonOJ Backend" cmd /k "python run.py"
) else (
    echo [跳过] 端口 8000 已被占用（后端可能已在运行；如刚更新过代码请重启该窗口）
)

rem 等待后端健康检查通过（最多 30 秒），确保 gRPC 网关已监听后再拉起节点
set /a hb=0
:wait_be
set /a hb+=1
if !hb! gtr 30 (
    echo [错误] 后端 30 秒内未就绪，请检查 Backend 窗口日志。
    pause
    exit /b 1
)
powershell -NoProfile -Command "try{Invoke-WebRequest -Uri 'http://127.0.0.1:8000/health' -UseBasicParsing -TimeoutSec 2|Out-Null;exit 0}catch{exit 1}" >nul 2>&1
if errorlevel 1 (
    timeout /t 1 /nobreak >nul
    goto wait_be
)
echo 后端就绪

rem ---------- 6. 本地判题节点容器（默认 1 个；配置见 .env.node.example → .env.node） ----------
echo [6/7] 启动判题节点容器...
if not exist "%~dp0.env.node" copy /y "%~dp0.env.node.example" "%~dp0.env.node" >nul
docker compose --env-file "%~dp0.env.node" -f "%~dp0docker-compose-node.yml" up -d --build 1>nul 2>&1
if errorlevel 1 (
    echo [警告] 判题节点容器启动失败，请检查 .env.node 与 Docker 日志（不影响其余服务，可稍后手动重试）。
) else (
    start "PigeonOJ Judge Node" cmd /k "docker compose --env-file %~dp0.env.node -f %~dp0docker-compose-node.yml logs -f"
)

rem ---------- 7. 启动前端 ----------
echo [7/7] 启动前端...

netstat -ano | findstr /c:":5173 " | findstr /c:"LISTENING" >nul 2>&1
if errorlevel 1 (
    cd /d "%~dp0src\frontend"
    start "PigeonOJ Frontend" cmd /k "npm run dev"
) else (
    echo [跳过] 端口 5173 已被占用（前端可能已在运行）
)

timeout /t 6 /nobreak >nul
start "" "http://localhost:5173"

echo.
echo ============================================
echo   启动完成！
echo   前端:  http://localhost:5173
echo   后端:  http://127.0.0.1:8000  （接口文档 /docs）
echo   判题节点:  Judge Node 窗口（gRPC 注册至后端网关 :50051）
echo   演示账号:  admin@pigeonoj.dev / Admin@123
echo   关闭弹出的窗口即停止对应服务。
echo ============================================
pause
