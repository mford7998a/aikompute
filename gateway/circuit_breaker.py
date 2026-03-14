"""
Circuit Breaker, Health Scoring, and Session Stickiness for provider pool.

Implements three features inspired by KiroGate and KiroProxy open-source work:

1. CIRCUIT BREAKER (CLOSED → OPEN → HALF-OPEN)
   - Tracks consecutive failures per provider.
   - After CB_FAILURE_THRESHOLD failures, opens the circuit for CB_OPEN_DURATION_S seconds.
   - After that cooldown, moves to HALF-OPEN: allows one probe request.
   - If the probe succeeds → CLOSED. If it fails → OPEN again.

2. HEALTH SCORE (0-100)
   - Maintained per provider using a short rolling window of successes/failures.
   - Starts at 100 (perfect). Each failure subtracts PENALTY, each success restores points.
   - Used by `best_available_providers()` to sort the auto-route order at request time.

3. SESSION STICKINESS
   - A session ID (from X-Session-ID header or synthesized from user+conversation context)
     is mapped to the provider that handled the first request in that session.
   - For SESSION_TTL_S seconds (default 60), subsequent requests in the same session
     go to the same provider, preventing context fragmentation across accounts.

All state is stored in Redis so it works correctly under multiple gateway workers.
"""

import json
import time
import logging
from typing import Optional

import redis.asyncio as redis
from config import settings

log = logging.getLogger(__name__)

# ── Tunables ────────────────────────────────────────────────────────────────

CB_FAILURE_THRESHOLD = 3        # consecutive failures → OPEN
CB_OPEN_DURATION_S   = 60       # seconds circuit stays OPEN
CB_HALF_OPEN_PROBE_TIMEOUT = 30 # seconds to wait for probe result before re-opening

HEALTH_WINDOW_S      = 300      # rolling window for health score (5 min)
HEALTH_MAX_SAMPLES   = 20       # keep last N outcomes per provider
HEALTH_FAILURE_PENALTY = 15     # points subtracted per failure
HEALTH_SUCCESS_REWARD  = 5      # points added per success (capped at 100)
HEALTH_MIN_SCORE       = 0

SESSION_TTL_S = 60              # seconds a session sticks to one provider

# ── Redis helpers ─────────────────────────────────────────────────────────

_redis: Optional[redis.Redis] = None


async def _get_redis() -> redis.Redis:
    global _redis
    if _redis is None:
        _redis = redis.from_url(settings.REDIS_URL, decode_responses=True)
    return _redis


# ── Key builders ─────────────────────────────────────────────────────────

def _cb_key(provider: str) -> str:
    return f"cb:{provider}"

def _health_key(provider: str) -> str:
    return f"health:{provider}"

def _session_key(session_id: str) -> str:
    return f"session:{session_id}"


# ══════════════════════════════════════════════════════════════════════════
# 1. CIRCUIT BREAKER
# ══════════════════════════════════════════════════════════════════════════

class CircuitState:
    CLOSED    = "closed"
    OPEN      = "open"
    HALF_OPEN = "half_open"


async def get_circuit_state(provider: str) -> str:
    """Return the current circuit breaker state for a provider."""
    r = await _get_redis()
    raw = await r.get(_cb_key(provider))
    if raw is None:
        return CircuitState.CLOSED

    data = json.loads(raw)
    state = data.get("state", CircuitState.CLOSED)

    if state == CircuitState.OPEN:
        opened_at = data.get("opened_at", 0)
        if time.time() - opened_at >= CB_OPEN_DURATION_S:
            # Transition to HALF-OPEN automatically
            await _set_circuit_state(provider, CircuitState.HALF_OPEN, data)
            return CircuitState.HALF_OPEN

    return state


async def _set_circuit_state(provider: str, state: str, existing: dict = None) -> None:
    r = await _get_redis()
    data = existing.copy() if existing else {}
    data["state"] = state
    if state == CircuitState.OPEN:
        data["opened_at"] = time.time()
        data["failures"]  = data.get("failures", 0)
    elif state == CircuitState.CLOSED:
        data["failures"] = 0
    await r.set(_cb_key(provider), json.dumps(data), ex=CB_OPEN_DURATION_S * 4)


async def record_provider_success(provider: str) -> None:
    """Call this after a successful upstream response."""
    r   = await _get_redis()
    raw = await r.get(_cb_key(provider))
    data = json.loads(raw) if raw else {}
    state = data.get("state", CircuitState.CLOSED)

    if state in (CircuitState.HALF_OPEN, CircuitState.OPEN):
        log.info("circuit_breaker: %s → CLOSED (probe succeeded)", provider)
    data["state"]    = CircuitState.CLOSED
    data["failures"] = 0
    await r.set(_cb_key(provider), json.dumps(data), ex=CB_OPEN_DURATION_S * 4)

    await _update_health(provider, success=True)


async def record_provider_failure(provider: str) -> None:
    """Call this after a failed upstream response."""
    r   = await _get_redis()
    raw = await r.get(_cb_key(provider))
    data = json.loads(raw) if raw else {}
    state    = data.get("state", CircuitState.CLOSED)
    failures = data.get("failures", 0) + 1

    data["failures"] = failures

    if state == CircuitState.HALF_OPEN:
        # Probe failed → re-open
        log.warning("circuit_breaker: %s → OPEN (probe failed)", provider)
        data["state"]     = CircuitState.OPEN
        data["opened_at"] = time.time()
    elif state == CircuitState.CLOSED and failures >= CB_FAILURE_THRESHOLD:
        log.warning(
            "circuit_breaker: %s → OPEN (%d consecutive failures)", provider, failures
        )
        data["state"]     = CircuitState.OPEN
        data["opened_at"] = time.time()
    # else still CLOSED, just incrementing counter

    await r.set(_cb_key(provider), json.dumps(data), ex=CB_OPEN_DURATION_S * 4)
    await _update_health(provider, success=False)


async def is_provider_available(provider: str) -> bool:
    """True if provider's circuit is CLOSED or HALF-OPEN (can attempt)."""
    state = await get_circuit_state(provider)
    return state != CircuitState.OPEN


async def get_all_circuit_states(providers: list[str]) -> dict[str, str]:
    """Batch-fetch circuit states for a list of providers."""
    r    = await _get_redis()
    keys = [_cb_key(p) for p in providers]
    raws = await r.mget(*keys)
    result = {}
    now    = time.time()
    for provider, raw in zip(providers, raws):
        if raw is None:
            result[provider] = CircuitState.CLOSED
            continue
        data  = json.loads(raw)
        state = data.get("state", CircuitState.CLOSED)
        if state == CircuitState.OPEN:
            if now - data.get("opened_at", 0) >= CB_OPEN_DURATION_S:
                state = CircuitState.HALF_OPEN
        result[provider] = state
    return result


# ══════════════════════════════════════════════════════════════════════════
# 2. HEALTH SCORE
# ══════════════════════════════════════════════════════════════════════════

async def _update_health(provider: str, success: bool) -> None:
    """Adjust health score based on a success/failure event."""
    r   = await _get_redis()
    key = _health_key(provider)
    raw = await r.get(key)
    data = json.loads(raw) if raw else {"score": 100, "samples": []}

    score   = data.get("score", 100)
    samples = data.get("samples", [])

    # Append outcome and trim to window
    samples.append({"t": time.time(), "ok": success})
    cutoff  = time.time() - HEALTH_WINDOW_S
    samples = [s for s in samples if s["t"] >= cutoff][-HEALTH_MAX_SAMPLES:]

    # Recompute score from scratch based on recent samples
    # (avoids drift from point-based editing over many restarts)
    if samples:
        ok_count  = sum(1 for s in samples if s["ok"])
        pct       = ok_count / len(samples)
        # Map 0-100% success rate → 0-100 score (with a slight bias toward 100 at 100%)
        score = int(round(pct * 100))
    else:
        score = 100  # no data → healthy assumption

    data["score"]   = score
    data["samples"] = samples
    await r.set(key, json.dumps(data), ex=HEALTH_WINDOW_S * 2)


async def get_health_score(provider: str) -> int:
    """Return 0-100 health score for a provider (100 = healthy, 0 = degraded)."""
    r   = await _get_redis()
    raw = await r.get(_health_key(provider))
    if raw is None:
        return 100
    data = json.loads(raw)
    return data.get("score", 100)


async def get_all_health_scores(providers: list[str]) -> dict[str, int]:
    """Batch-fetch health scores for a list of providers."""
    r    = await _get_redis()
    keys = [_health_key(p) for p in providers]
    raws = await r.mget(*keys)
    result = {}
    for provider, raw in zip(providers, raws):
        if raw is None:
            result[provider] = 100
        else:
            data = json.loads(raw)
            result[provider] = data.get("score", 100)
    return result


async def best_available_providers(ordered_providers: list[str]) -> list[str]:
    """
    Return `ordered_providers` re-ranked by:
      1. Filter out OPEN circuits entirely.
      2. Sort remainder by health score (desc), with HALF-OPEN after CLOSED at same score.

    Falls back to the original order if Redis is unavailable.
    """
    try:
        states = await get_all_circuit_states(ordered_providers)
        scores = await get_all_health_scores(ordered_providers)
    except Exception as exc:
        log.warning("circuit_breaker: Redis unavailable, using default order: %s", exc)
        return ordered_providers

    available = [
        p for p in ordered_providers
        if states.get(p, CircuitState.CLOSED) != CircuitState.OPEN
    ]

    # Sort: CLOSED before HALF-OPEN at the same score, higher score first
    def sort_key(p):
        state = states.get(p, CircuitState.CLOSED)
        score = scores.get(p, 100)
        order = 0 if state == CircuitState.CLOSED else 1  # HALF-OPEN penalised
        return (-score, order)  # negate score so highest sorts first

    available.sort(key=sort_key)
    return available


# ══════════════════════════════════════════════════════════════════════════
# 3. SESSION STICKINESS
# ══════════════════════════════════════════════════════════════════════════

async def get_session_provider(session_id: str) -> Optional[str]:
    """
    Look up which provider is pinned to this session.
    Returns None if no pin exists (first request in session).
    """
    if not session_id:
        return None
    r   = await _get_redis()
    raw = await r.get(_session_key(session_id))
    return raw  # raw is the provider string or None


async def pin_session_provider(session_id: str, provider: str) -> None:
    """
    Pin a session to a provider for SESSION_TTL_S seconds.
    Each call refreshes the TTL (keeps sticky as long as conversation is active).
    """
    if not session_id:
        return
    r = await _get_redis()
    await r.set(_session_key(session_id), provider, ex=SESSION_TTL_S)


async def clear_session_provider(session_id: str) -> None:
    """Explicitly clear a session pin (e.g. on error or explicit reset)."""
    if not session_id:
        return
    r = await _get_redis()
    await r.delete(_session_key(session_id))
