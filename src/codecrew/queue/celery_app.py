import os
from celery import Celery
from dotenv import load_dotenv

load_dotenv(override=True)

redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# Fix for Upstash/Redis Cloud secure connections throwing ValueError in Celery
if redis_url.startswith("rediss://") and "ssl_cert_reqs" not in redis_url:
    separator = "&" if "?" in redis_url else "?"
    redis_url += f"{separator}ssl_cert_reqs=CERT_NONE"

app = Celery(
    "codecrew_queue",
    broker=redis_url,
    backend=redis_url,
    include=["codecrew.queue.tasks"]
)

# Configuration to protect rate limits & ensure sequential processing
app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    worker_concurrency=1,            # CRITICAL: process only 1 task at a time per worker instance!
    task_acks_late=True,             # Acknowledge task only after completion
    worker_prefetch_multiplier=1     # Don't reserve extra tasks
)
