"""开发启动入口：uvicorn app:app --reload（生产用 Dockerfile CMD / gunicorn）。

监听端口取配置链（进程环境变量 > .env > backend.toml [server] port，默认 8000）。
"""
import uvicorn
from uvicorn.config import LOGGING_CONFIG

from app.settings.config import get_settings

if __name__ == "__main__":
    # 调整 uvicorn 默认日志格式：带时间戳，便于本地排查
    LOGGING_CONFIG["formatters"]["default"]["fmt"] = "%(asctime)s - %(levelname)s - %(message)s"
    LOGGING_CONFIG["formatters"]["default"]["datefmt"] = "%Y-%m-%d %H:%M:%S"
    LOGGING_CONFIG["formatters"]["access"][
        "fmt"
    ] = '%(asctime)s - %(levelname)s - %(client_addr)s - "%(request_line)s" %(status_code)s'
    LOGGING_CONFIG["formatters"]["access"]["datefmt"] = "%Y-%m-%d %H:%M:%S"

    # proxy_headers：开发态本地直连无反代也无碍——XFF 不存在时 client.host 即真实地址；
    # forwarded_allow_ips 限定仅本机回环可作为可信代理来源
    uvicorn.run(
        "app:app",
        host="127.0.0.1",
        port=get_settings().server_port,
        reload=True,
        log_config=LOGGING_CONFIG,
        proxy_headers=True,
        forwarded_allow_ips="127.0.0.1",
    )
