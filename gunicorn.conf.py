import os

# Render injects PORT dynamically -- must bind to it, never hardcode a port.
bind = f"0.0.0.0:{os.environ.get('PORT', '8000')}"

# NOTE: do NOT default this to a multiprocessing.cpu_count()-based formula. In a
# container, cpu_count() reports the HOST's core count, not what the plan actually
# allocates -- on a small instance (e.g. Render's Starter, ~512MB RAM) that formula
# spawns far more full Django worker processes than fit in memory, and they get
# OOM-killed in a crash loop (CRITICAL WORKER TIMEOUT -> SIGKILL, repeating forever).
# 2 workers x 2 threads is a safe default for small instances; raise GUNICORN_WORKERS
# explicitly once you know the plan's actual RAM can support more.
workers = int(os.environ.get("GUNICORN_WORKERS", 2))
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
