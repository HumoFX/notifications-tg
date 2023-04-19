from typing import AsyncIterator

from aioredis import Redis
from app.core.config import settings


def create_redis_pool():
    """Create redis pool."""
    redis = Redis.from_url(f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}")
    return redis
