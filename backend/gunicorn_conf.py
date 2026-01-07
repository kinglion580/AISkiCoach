"""
Gunicorn 生产环境配置文件
根据 CPU 核心数动态调整 worker 数量

配置说明：
- 本文件使用环境变量配置，对应 app.core.config.Settings 中的字段
- 环境变量可在 .env 文件中设置
- 配置映射关系：
  GUNICORN_WORKERS → Settings.GUNICORN_WORKERS
  GUNICORN_WORKER_CONNECTIONS → Settings.GUNICORN_WORKER_CONNECTIONS
  GUNICORN_MAX_REQUESTS → Settings.GUNICORN_MAX_REQUESTS
  GUNICORN_TIMEOUT → Settings.GUNICORN_TIMEOUT
  等等...
"""
import multiprocessing
import os

# 绑定地址
bind = "0.0.0.0:8000"

# Worker 配置
# 推荐公式: (2 x CPU核心数) + 1
# 可通过 .env 中的 GUNICORN_WORKERS 环境变量覆盖
workers = int(os.getenv("GUNICORN_WORKERS", (2 * multiprocessing.cpu_count()) + 1))

# Worker 类型 - 使用 Uvicorn 的异步 worker
worker_class = "uvicorn.workers.UvicornWorker"

# Worker 连接数
worker_connections = int(os.getenv("GUNICORN_WORKER_CONNECTIONS", 1000))

# 请求处理配置
# 在处理 max_requests 个请求后重启 worker（防止内存泄漏）
max_requests = int(os.getenv("GUNICORN_MAX_REQUESTS", 1000))
# 添加随机抖动，避免所有 worker 同时重启
max_requests_jitter = int(os.getenv("GUNICORN_MAX_REQUESTS_JITTER", 50))

# 超时配置
timeout = int(os.getenv("GUNICORN_TIMEOUT", 120))
keepalive = int(os.getenv("GUNICORN_KEEPALIVE", 5))
graceful_timeout = int(os.getenv("GUNICORN_GRACEFUL_TIMEOUT", 30))

# 预加载应用代码（节省内存，加快启动）
preload_app = True

# 日志配置
accesslog = "-"  # 输出到 stdout
errorlog = "-"   # 输出到 stderr
loglevel = os.getenv("GUNICORN_LOG_LEVEL", "info")
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# 进程命名
proc_name = "ai-skicoach-backend"

# 服务器钩子（可选）
def on_starting(server):
    """服务器启动时调用"""
    server.log.info(f"Starting AI SkiCoach Backend with {workers} workers")

def worker_int(worker):
    """Worker 收到 SIGINT/SIGQUIT 时调用"""
    worker.log.info(f"Worker {worker.pid} received SIGINT/SIGQUIT")

def on_exit(server):
    """服务器关闭时调用"""
    server.log.info("AI SkiCoach Backend shutting down")
