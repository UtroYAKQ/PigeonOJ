"""开发启动入口：uvicorn app:app --reload（生产用 Dockerfile CMD / gunicorn）。"""
import uvicorn
from uvicorn.config import LOGGING_CONFIG

if __name__ == "__main__":
    # 调整 uvicorn 默认日志格式：带时间戳，便于本地排查
    LOGGING_CONFIG["formatters"]["default"]["fmt"] = "%(asctime)s - %(levelname)s - %(message)s"
    LOGGING_CONFIG["formatters"]["default"]["datefmt"] = "%Y-%m-%d %H:%M:%S"
    LOGGING_CONFIG["formatters"]["access"][
        "fmt"
    ] = '%(asctime)s - %(levelname)s - %(client_addr)s - "%(request_line)s" %(status_code)s'
    LOGGING_CONFIG["formatters"]["access"]["datefmt"] = "%Y-%m-%d %H:%M:%S"

    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=True, log_config=LOGGING_CONFIG)
