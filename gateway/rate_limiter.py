"""
Rate limiting using Redis sliding window.
"""
import time
from typing import Optional

import redis.asyncio as redis
from fastapi import HTTPException
from config import settings

_redis: Optional[redis.Redis] = None


async def get_redis() -> redis.Redis:
    global _redis
    if _redis is None:
        _redis = redis.from_url(settings.REDIS_URL, decode_responses=True)
    return _redis


async def check_rate_limit(
    user_id: str,
    api_key_id: str,
    rpm_limit: int,
    tpm_limit: int,
    estimated_tokens: int = 0,
) -> None:
    """
    Check rate limits using Redis sliding window counters.
    Raises HTTPException 429 if limits are exceeded.
    """
    r = await get_redis()
    now = time.time()
    window_start = now - 60  # 1-minute window

    pipe = r.pipeline()

    # -- Requests Per Minute (RPM) --
    rpm_key = f"ratelimit:rpm:{api_key_id}"
    pipe.zremrangebyscore(rpm_key, 0, window_start)
    pipe.zadd(rpm_key, {f"{now}": now})
    pipe.zcard(rpm_key)
    pipe.expire(rpm_key, 120)

    # -- Tokens Per Minute (TPM) --
    tpm_key = f"ratelimit:tpm:{api_key_id}"
    pipe.get(tpm_key)

    results = await pipe.execute()

    current_rpm = results[2]  # zcard result
    current_tpm = int(results[4] or 0)  # get result

    if current_rpm > rpm_limit:
        # Remove the request we just added
        await r.zrem(rpm_key, f"{now}")
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded: {current_rpm}/{rpm_limit} requests per minute",
            headers={"Retry-After": "60"},
        )

    if current_tpm + estimated_tokens > tpm_limit:
        await r.zrem(rpm_key, f"{now}")
        raise HTTPException(
            status_code=429,
            detail=f"Token rate limit exceeded: {current_tpm + estimated_tokens}/{tpm_limit} tokens per minute",
            headers={"Retry-After": "60"},
        )


async def record_token_usage(api_key_id: str, tokens: int) -> None:
    """Record token usage for TPM rate limiting."""
    r = await get_redis()
    tpm_key = f"ratelimit:tpm:{api_key_id}"
    await r.incrby(tpm_key, tokens)
    await r.expire(tpm_key, 60)
