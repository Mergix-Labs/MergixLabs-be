import multiprocessing
import os

# Render injects PORT dynamically -- must bind to it, never hardcode a port.
bind = f"0.0.0.0:{os.environ.get('PORT', '8000')}"

workers = int(os.environ.get("GUNICORN_WORKERS", multiprocessing.cpu_count() * 2 + 1))
threads = int(os.environ.get("GUNICORN_THREADS", 2))
worker_class = "gthread"

timeout = int(os.environ.get("GUNICORN_TIMEOUT", 30))
graceful_timeout = int(os.environ.get("GUNICORN_GRACEFUL_TIMEOUT", 30))
keepalive = int(os.environ.get("GUNICORN_KEEPALIVE", 5))

# Recycle workers periodically to guard against slow memory leaks.
max_requests = int(os.environ.get("GUNICORN_MAX_REQUESTS", 1000))
max_requests_jitter = int(os.environ.get("GUNICORN_MAX_REQUESTS_JITTER", 50))

accesslog = "-"
errorlog = "-"
loglevel = os.environ.get("GUNICORN_LOG_LEVEL", "info")
