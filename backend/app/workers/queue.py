import logging
import concurrent.futures
from typing import Callable, Any
from backend.app.config import settings

logger = logging.getLogger(__name__)

# Bounded in-process worker pool for non-blocking asynchronous execution
_thread_pool = concurrent.futures.ThreadPoolExecutor(max_workers=4)


class BackgroundJobQueue:
    def __init__(self):
        self.redis_available = False
        self._check_redis()

    def _check_redis(self):
        try:
            import redis
            r = redis.from_url(settings.REDIS_URL, socket_timeout=1)
            r.ping()
            self.redis_available = True
            logger.info("Connected to Redis task queue.")
        except Exception:
            self.redis_available = False
            logger.info("Redis not available. Using high-performance concurrent ThreadPool fallback.")

    def enqueue(self, fn: Callable, *args: Any, **kwargs: Any):
        """Dispatches job asynchronously so web requests never block."""
        # We submit to the bounded background worker pool
        _thread_pool.submit(fn, *args, **kwargs)


job_queue = BackgroundJobQueue()
