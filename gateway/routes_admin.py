"""
Admin API Routes: Business analytics, forecasting, user management, and provider monitoring.

Requires admin JWT token (is_admin=true) for all endpoints.
"""
import math
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from auth import verify_jwt_token
from database import get_db
from circuit_breaker import (
    get_all_circuit_states,
    get_all_health_scores,
    CircuitState,
)
from proxy import AUTO_ROUTE_ORDER

router = APIRouter()


def require_admin(jwt: dict = Depends(verify_jwt_token)):
    """Dependency that ensures the user is an admin."""
    if not jwt.get("admin"):
        raise HTTPException(403, "Admin access required")
    return jwt


# ============================================
# Dashboard Summary — Single endpoint for the overview
# ============================================

@router.get("/admin/dashboard")
async def admin_dashboard(
    admin: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Complete dashboard summary with all key metrics."""
    now = datetime.now(timezone.utc)

    # -- User Stats --
    users = await db.execute(text("""
        SELECT 
            COUNT(*) as total_users,
            COUNT(*) FILTER (WHERE created_at > NOW() - INTERVAL '24 hours') as new_today,
            COUNT(*) FILTER (WHERE created_at > NOW() - INTERVAL '7 days') as new_this_week,
            COUNT(*) FILTER (WHERE created_at > NOW() - INTERVAL '30 days') as new_this_month,
            SUM(credit_balance) as total_credit_balance
        FROM users WHERE is_active = true
    """))
    user_stats = dict(users.fetchone()._mapping)

    # Active users (made a request)
    active = await db.execute(text("""
        SELECT 
            COUNT(DISTINCT user_id) FILTER (WHERE created_at > NOW() - INTERVAL '24 hours') as active_today,
            COUNT(DISTINCT user_id) FILTER (WHERE created_at > NOW() - INTERVAL '7 days') as active_7d,
            COUNT(DISTINCT user_id) FILTER (WHERE created_at > NOW() - INTERVAL '30 days') as active_30d
        FROM usage_logs
    """))
    active_stats = dict(active.fetchone()._mapping)

    # -- Token Stats (all time, 30d, 7d, today) --
    tokens = await db.execute(text("""
        SELECT
            COALESCE(SUM(total_tokens), 0) as tokens_all_time,
            COALESCE(SUM(total_tokens) FILTER (WHERE created_at > NOW() - INTERVAL '30 days'), 0) as tokens_30d,
            COALESCE(SUM(total_tokens) FILTER (WHERE created_at > NOW() - INTERVAL '7 days'), 0) as tokens_7d,
            COALESCE(SUM(total_tokens) FILTER (WHERE created_at > NOW() - INTERVAL '24 hours'), 0) as tokens_today,
            COALESCE(SUM(input_tokens), 0) as input_tokens_all,
            COALESCE(SUM(output_tokens), 0) as output_tokens_all,
            COUNT(*) as requests_all_time,
            COUNT(*) FILTER (WHERE created_at > NOW() - INTERVAL '24 hours') as requests_today,
            COUNT(*) FILTER (WHERE created_at > NOW() - INTERVAL '30 days') as requests_30d,
            COALESCE(AVG(latency_ms) FILTER (WHERE status = 'success'), 0)::int as avg_latency_ms,
            COUNT(*) FILTER (WHERE status = 'error') as errors_all,
            COUNT(*) FILTER (WHERE status = 'error' AND created_at > NOW() - INTERVAL '24 hours') as errors_today
        FROM usage_logs
    """))
    token_stats = dict(tokens.fetchone()._mapping)

    # -- Financial Stats --
    financials = await db.execute(text("""
        SELECT
            COALESCE(SUM(amount) FILTER (WHERE transaction_type = 'purchase'), 0) as total_revenue_credits,
            COALESCE(SUM(amount) FILTER (WHERE transaction_type = 'purchase' AND created_at > NOW() - INTERVAL '30 days'), 0) as revenue_30d,
            COALESCE(SUM(amount) FILTER (WHERE transaction_type = 'purchase' AND created_at > NOW() - INTERVAL '7 days'), 0) as revenue_7d,
            COALESCE(SUM(amount) FILTER (WHERE transaction_type = 'purchase' AND created_at > NOW() - INTERVAL '24 hours'), 0) as revenue_today,
            COALESCE(SUM(ABS(amount)) FILTER (WHERE transaction_type = 'usage'), 0) as total_usage_credits,
            COALESCE(SUM(ABS(amount)) FILTER (WHERE transaction_type = 'usage' AND created_at > NOW() - INTERVAL '30 days'), 0) as usage_30d,
            COUNT(*) FILTER (WHERE transaction_type = 'purchase') as total_purchases
        FROM credit_transactions
    """))
    financial_stats = dict(financials.fetchone()._mapping)

    # -- Provider Stats --
    providers = await db.execute(text("""
        SELECT
            provider_type,
            COUNT(*) as request_count,
            COALESCE(SUM(total_tokens), 0) as total_tokens,
            COUNT(*) FILTER (WHERE status = 'error') as error_count,
            COALESCE(AVG(latency_ms) FILTER (WHERE status = 'success'), 0)::int as avg_latency,
            MAX(created_at) as last_request
        FROM usage_logs
        WHERE created_at > NOW() - INTERVAL '24 hours'
        GROUP BY provider_type
        ORDER BY request_count DESC
    """))
    provider_stats = []
    for row in providers.fetchall():
        r = dict(row._mapping)
        r["last_request"] = str(r["last_request"]) if r["last_request"] else None
        total = r["request_count"] or 1
        r["error_rate"] = round((r["error_count"] / total) * 100, 1)
        provider_stats.append(r)

    # -- Error rate --
    total_requests = token_stats["requests_all_time"] or 1
    error_rate = round((token_stats["errors_all"] / total_requests) * 100, 2)

    return {
        "users": {
            **user_stats,
            **active_stats,
            "total_credit_balance_display": f"{(user_stats['total_credit_balance'] or 0) / 1_000_000:.2f}",
        },
        "tokens": {
            **token_stats,
            "avg_tokens_per_request": round(token_stats["tokens_all_time"] / max(token_stats["requests_all_time"], 1)),
            "input_output_ratio": round(token_stats["input_tokens_all"] / max(token_stats["output_tokens_all"], 1), 2),
        },
        "financials": {
            **financial_stats,
            "total_revenue_display": f"${(financial_stats['total_revenue_credits'] or 0) / 1_000_000:.2f}",
            "revenue_30d_display": f"${(financial_stats['revenue_30d'] or 0) / 1_000_000:.2f}",
            "arpu": round((financial_stats["total_revenue_credits"] or 0) / max(user_stats["total_users"], 1) / 1_000_000, 2),
        },
        "providers": provider_stats,
        "health": {
            "error_rate": error_rate,
            "avg_latency_ms": token_stats["avg_latency_ms"],
            "errors_today": token_stats["errors_today"],
        },
        "generated_at": now.isoformat(),
    }


# ============================================
# Daily Trends — Token usage, requests, revenue per day
# ============================================

@router.get("/admin/trends")
async def admin_trends(
    days: int = Query(default=30, le=365),
    admin: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Daily trends for tokens, requests, users, and revenue."""

    # Token + request trends
    usage_trend = await db.execute(text("""
        SELECT 
            DATE(created_at) as date,
            COUNT(*) as requests,
            COALESCE(SUM(total_tokens), 0) as tokens,
            COALESCE(SUM(input_tokens), 0) as input_tokens,
            COALESCE(SUM(output_tokens), 0) as output_tokens,
            COALESCE(SUM(credits_charged), 0) as credits_charged,
            COUNT(DISTINCT user_id) as unique_users,
            COUNT(*) FILTER (WHERE status = 'error') as errors,
            COALESCE(AVG(latency_ms) FILTER (WHERE status = 'success'), 0)::int as avg_latency
        FROM usage_logs
        WHERE created_at > NOW() - make_interval(days => :days)
        GROUP BY DATE(created_at)
        ORDER BY date
    """), {"days": days})

    daily = []
    for row in usage_trend.fetchall():
        r = dict(row._mapping)
        r["date"] = str(r["date"])
        daily.append(r)

    # Revenue trend
    revenue_trend = await db.execute(text("""
        SELECT 
            DATE(created_at) as date,
            COALESCE(SUM(amount) FILTER (WHERE transaction_type = 'purchase'), 0) as revenue,
            COALESCE(SUM(ABS(amount)) FILTER (WHERE transaction_type = 'usage'), 0) as cost_to_users,
            COUNT(*) FILTER (WHERE transaction_type = 'purchase') as purchases
        FROM credit_transactions
        WHERE created_at > NOW() - make_interval(days => :days)
        GROUP BY DATE(created_at)
        ORDER BY date
    """), {"days": days})

    revenue_daily = []
    for row in revenue_trend.fetchall():
        r = dict(row._mapping)
        r["date"] = str(r["date"])
        revenue_daily.append(r)

    # New user registrations per day
    signups = await db.execute(text("""
        SELECT DATE(created_at) as date, COUNT(*) as new_users
        FROM users
        WHERE created_at > NOW() - make_interval(days => :days)
        GROUP BY DATE(created_at)
        ORDER BY date
    """), {"days": days})

    signup_daily = []
    for row in signups.fetchall():
        r = dict(row._mapping)
        r["date"] = str(r["date"])
        signup_daily.append(r)

    return {
        "usage": daily,
        "revenue": revenue_daily,
        "signups": signup_daily,
    }


# ============================================
# Forecasting — Predict future token usage + account needs
# ============================================

@router.get("/admin/forecast")
async def admin_forecast(
    admin: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Forecast future token usage and account needs using linear regression
    on the last 30 days of daily data.
    """
    # Get last 30 days of daily token usage
    result = await db.execute(text("""
        SELECT 
            DATE(created_at) as date,
            COALESCE(SUM(total_tokens), 0) as tokens,
            COUNT(*) as requests,
            COUNT(DISTINCT user_id) as users
        FROM usage_logs
        WHERE created_at > NOW() - INTERVAL '30 days'
          AND status = 'success'
        GROUP BY DATE(created_at)
        ORDER BY date
    """))
    daily_data = [dict(row._mapping) for row in result.fetchall()]

    if len(daily_data) < 3:
        return {
            "message": "Not enough data for forecasting (need at least 3 days)",
            "forecast": [],
            "account_needs": {},
        }

    # Linear regression on token usage
    n = len(daily_data)
    x_vals = list(range(n))
    y_tokens = [d["tokens"] for d in daily_data]
    y_requests = [d["requests"] for d in daily_data]
    y_users = [d["users"] for d in daily_data]

    def linear_regression(x, y):
        n = len(x)
        sum_x = sum(x)
        sum_y = sum(y)
        sum_xy = sum(a * b for a, b in zip(x, y))
        sum_x2 = sum(a ** 2 for a in x)
        denom = n * sum_x2 - sum_x ** 2
        if denom == 0:
            return sum_y / n, 0  # flat line
        slope = (n * sum_xy - sum_x * sum_y) / denom
        intercept = (sum_y - slope * sum_x) / n
        # R-squared
        y_mean = sum_y / n
        ss_tot = sum((yi - y_mean) ** 2 for yi in y)
        ss_res = sum((yi - (intercept + slope * xi)) ** 2 for xi, yi in zip(x, y))
        r_squared = 1 - (ss_res / max(ss_tot, 1))
        return intercept, slope, r_squared

    tok_intercept, tok_slope, tok_r2 = linear_regression(x_vals, y_tokens)
    req_intercept, req_slope, req_r2 = linear_regression(x_vals, y_requests)
    usr_intercept, usr_slope, usr_r2 = linear_regression(x_vals, y_users)

    # Forecast next 30 days
    forecast = []
    base_date = datetime.strptime(str(daily_data[-1]["date"]), "%Y-%m-%d")
    for i in range(1, 31):
        day_idx = n + i - 1
        pred_tokens = max(0, tok_intercept + tok_slope * day_idx)
        pred_requests = max(0, req_intercept + req_slope * day_idx)
        pred_users = max(0, usr_intercept + usr_slope * day_idx)
        forecast_date = base_date + timedelta(days=i)
        forecast.append({
            "date": forecast_date.strftime("%Y-%m-%d"),
            "predicted_tokens": round(pred_tokens),
            "predicted_requests": round(pred_requests),
            "predicted_active_users": round(pred_users),
        })

    # Current daily average
    avg_daily_tokens = sum(y_tokens) / n
    predicted_daily_30d = forecast[-1]["predicted_tokens"] if forecast else avg_daily_tokens

    # Account needs estimation
    # Typical free account limits (configurable):
    ACCOUNT_DAILY_LIMITS = {
        "gemini-cli-oauth": 1_500_000,      # ~1.5M tokens/day per Gemini account
        "gemini-antigravity": 1_000_000,     # ~1M tokens/day per Antigravity account
        "claude-kiro-oauth": 500_000,        # ~500K tokens/day per Kiro account
        "openai-qwen-oauth": 800_000,        # ~800K tokens/day per Qwen account
    }

    # Get current provider distribution
    provider_dist = await db.execute(text("""
        SELECT provider_type, 
               COALESCE(SUM(total_tokens), 0) as tokens,
               COUNT(*) as requests
        FROM usage_logs
        WHERE created_at > NOW() - INTERVAL '7 days' AND status = 'success'
        GROUP BY provider_type
    """))
    provider_share = {}
    total_provider_tokens = 0
    for row in provider_dist.fetchall():
        provider_share[row.provider_type] = row.tokens
        total_provider_tokens += row.tokens

    account_needs = {}
    for provider, daily_limit in ACCOUNT_DAILY_LIMITS.items():
        share = provider_share.get(provider, 0) / max(total_provider_tokens, 1)
        current_daily = avg_daily_tokens * share
        forecast_daily = predicted_daily_30d * share
        
        accounts_needed_now = max(1, math.ceil(current_daily / daily_limit))
        accounts_needed_30d = max(1, math.ceil(forecast_daily / daily_limit))

        account_needs[provider] = {
            "daily_limit_per_account": daily_limit,
            "current_daily_tokens": round(current_daily),
            "forecast_daily_tokens_30d": round(forecast_daily),
            "accounts_needed_now": accounts_needed_now,
            "accounts_needed_30d": accounts_needed_30d,
            "traffic_share_pct": round(share * 100, 1),
        }

    # Growth metrics
    week1_avg = sum(y_tokens[:7]) / min(7, len(y_tokens[:7])) if len(y_tokens) >= 7 else avg_daily_tokens
    week4_avg = sum(y_tokens[-7:]) / len(y_tokens[-7:])
    growth_rate = ((week4_avg - week1_avg) / max(week1_avg, 1)) * 100

    return {
        "historical_summary": {
            "avg_daily_tokens": round(avg_daily_tokens),
            "avg_daily_requests": round(sum(y_requests) / n),
            "avg_daily_users": round(sum(y_users) / n),
            "total_tokens_30d": sum(y_tokens),
            "growth_rate_pct": round(growth_rate, 1),
            "data_points": n,
        },
        "model_quality": {
            "tokens_r_squared": round(tok_r2, 3),
            "requests_r_squared": round(req_r2, 3),
            "users_r_squared": round(usr_r2, 3),
        },
        "forecast": forecast,
        "account_needs": account_needs,
        "prediction_30d": {
            "predicted_daily_tokens": round(predicted_daily_30d),
            "predicted_monthly_tokens": round(predicted_daily_30d * 30),
            "total_accounts_needed": sum(a["accounts_needed_30d"] for a in account_needs.values()),
        },
    }


# ============================================
# All Users — Paginated list with usage stats
# ============================================

@router.get("/admin/users")
async def admin_list_users(
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=50, le=200),
    sort: str = Query(default="created_at", pattern="^(created_at|credit_balance|total_tokens|last_active)$"),
    order: str = Query(default="desc", pattern="^(asc|desc)$"),
    search: str = Query(default=""),
    admin: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """List all users with their usage statistics."""
    offset = (page - 1) * per_page
    search_clause = ""
    params = {"limit": per_page, "offset": offset}

    if search:
        search_clause = "AND (u.email ILIKE :search OR u.display_name ILIKE :search)"
        params["search"] = f"%{search}%"

    # Map sort field to actual column
    sort_map = {
        "created_at": "u.created_at",
        "credit_balance": "u.credit_balance",
        "total_tokens": "COALESCE(usage.total_tokens, 0)",
        "last_active": "usage.last_active",
    }
    sort_col = sort_map.get(sort, "u.created_at")

    result = await db.execute(text(f"""
        SELECT 
            u.id, u.email, u.display_name, u.credit_balance, u.is_active, u.is_admin,
            u.created_at,
            COALESCE(usage.total_requests, 0) as total_requests,
            COALESCE(usage.total_tokens, 0) as total_tokens,
            COALESCE(usage.total_credits_used, 0) as total_credits_used,
            COALESCE(usage.requests_today, 0) as requests_today,
            COALESCE(usage.tokens_today, 0) as tokens_today,
            usage.last_active,
            COALESCE(keys.key_count, 0) as api_key_count
        FROM users u
        LEFT JOIN LATERAL (
            SELECT 
                COUNT(*) as total_requests,
                SUM(total_tokens) as total_tokens,
                SUM(credits_charged) as total_credits_used,
                COUNT(*) FILTER (WHERE ul.created_at > NOW() - INTERVAL '24 hours') as requests_today,
                COALESCE(SUM(total_tokens) FILTER (WHERE ul.created_at > NOW() - INTERVAL '24 hours'), 0) as tokens_today,
                MAX(ul.created_at) as last_active
            FROM usage_logs ul WHERE ul.user_id = u.id
        ) usage ON true
        LEFT JOIN LATERAL (
            SELECT COUNT(*) as key_count FROM api_keys ak WHERE ak.user_id = u.id AND ak.is_active = true
        ) keys ON true
        WHERE 1=1 {search_clause}
        ORDER BY {sort_col} {order} NULLS LAST
        LIMIT :limit OFFSET :offset
    """), params)

    users = []
    for row in result.fetchall():
        r = dict(row._mapping)
        r["id"] = str(r["id"])
        r["created_at"] = str(r["created_at"])
        r["last_active"] = str(r["last_active"]) if r["last_active"] else None
        r["credit_balance_display"] = f"{(r['credit_balance'] or 0) / 1_000_000:.2f}"
        users.append(r)

    # Total count
    count_result = await db.execute(text(f"""
        SELECT COUNT(*) FROM users u WHERE 1=1 {search_clause}
    """), params)
    total = count_result.scalar()

    return {
        "users": users,
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": math.ceil(total / per_page),
    }


# ============================================
# Per-User Detail
# ============================================

@router.get("/admin/users/{user_id}")
async def admin_user_detail(
    user_id: str,
    admin: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Detailed view of a specific user."""
    user = await db.execute(text("""
        SELECT id, email, display_name, credit_balance, is_active, is_admin, 
               stripe_customer_id, created_at, updated_at
        FROM users WHERE id = :uid
    """), {"uid": user_id})
    u = user.fetchone()
    if not u:
        raise HTTPException(404, "User not found")

    # Recent usage
    usage = await db.execute(text("""
        SELECT request_id, model_requested, model_used, provider_type,
               input_tokens, output_tokens, total_tokens, credits_charged,
               latency_ms, status, error_message, created_at
        FROM usage_logs WHERE user_id = :uid
        ORDER BY created_at DESC LIMIT 50
    """), {"uid": user_id})

    recent = []
    for row in usage.fetchall():
        r = dict(row._mapping)
        r["created_at"] = str(r["created_at"])
        recent.append(r)

    # Daily usage for this user
    daily = await db.execute(text("""
        SELECT DATE(created_at) as date, COUNT(*) as requests,
               SUM(total_tokens) as tokens, SUM(credits_charged) as credits
        FROM usage_logs WHERE user_id = :uid
        GROUP BY DATE(created_at) ORDER BY date DESC LIMIT 30
    """), {"uid": user_id})

    daily_data = []
    for row in daily.fetchall():
        r = dict(row._mapping)
        r["date"] = str(r["date"])
        daily_data.append(r)

    return {
        "user": {
            "id": str(u.id),
            "email": u.email,
            "display_name": u.display_name,
            "credit_balance": u.credit_balance,
            "credit_balance_display": f"{u.credit_balance / 1_000_000:.2f}",
            "is_active": u.is_active,
            "is_admin": u.is_admin,
            "created_at": str(u.created_at),
        },
        "recent_requests": recent,
        "daily_usage": daily_data,
    }


# ============================================
# Provider Health — Real-time account status
# ============================================

@router.get("/admin/providers")
async def admin_providers(
    admin: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Provider usage stats with health indicators."""
    # Last 24h stats per provider
    result = await db.execute(text("""
        SELECT 
            provider_type,
            COUNT(*) as requests_24h,
            SUM(total_tokens) as tokens_24h,
            COUNT(*) FILTER (WHERE status = 'error') as errors_24h,
            AVG(latency_ms) FILTER (WHERE status = 'success') as avg_latency,
            MIN(created_at) as first_request,
            MAX(created_at) as last_request
        FROM usage_logs
        WHERE created_at > NOW() - INTERVAL '24 hours'
        GROUP BY provider_type
        ORDER BY tokens_24h DESC
    """))

    providers = []
    for row in result.fetchall():
        r = dict(row._mapping)
        r["first_request"] = str(r["first_request"])
        r["last_request"] = str(r["last_request"])
        r["avg_latency"] = round(r["avg_latency"]) if r["avg_latency"] else 0
        r["error_rate"] = round((r["errors_24h"] / max(r["requests_24h"], 1)) * 100, 1)
        r["health"] = "healthy" if r["error_rate"] < 5 else ("degraded" if r["error_rate"] < 20 else "unhealthy")
        providers.append(r)

    # Per-hour breakdown (last 24h)
    hourly = await db.execute(text("""
        SELECT 
            DATE_TRUNC('hour', created_at) as hour,
            provider_type,
            COUNT(*) as requests,
            SUM(total_tokens) as tokens
        FROM usage_logs
        WHERE created_at > NOW() - INTERVAL '24 hours'
        GROUP BY DATE_TRUNC('hour', created_at), provider_type
        ORDER BY hour
    """))
    hourly_data = []
    for row in hourly.fetchall():
        r = dict(row._mapping)
        r["hour"] = str(r["hour"])
        hourly_data.append(r)

    return {"providers": providers, "hourly": hourly_data}


# ============================================
# Top Models — Most used models
# ============================================

@router.get("/admin/models")
async def admin_model_stats(
    days: int = Query(default=30),
    admin: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Usage stats per model."""
    result = await db.execute(text("""
        SELECT 
            model_used as model,
            provider_type,
            COUNT(*) as requests,
            SUM(total_tokens) as tokens,
            SUM(credits_charged) as credits,
            AVG(latency_ms) FILTER (WHERE status = 'success') as avg_latency,
            COUNT(DISTINCT user_id) as unique_users
        FROM usage_logs
        WHERE created_at > NOW() - make_interval(days => :days)
        GROUP BY model_used, provider_type
        ORDER BY tokens DESC
    """), {"days": days})

    models = []
    for row in result.fetchall():
        r = dict(row._mapping)
        r["avg_latency"] = round(r["avg_latency"]) if r["avg_latency"] else 0
        models.append(r)

    return {"models": models}


# ============================================
# Admin Actions
# ============================================

@router.post("/admin/users/{user_id}/credits")
async def admin_adjust_credits(
    user_id: str,
    amount: int = Query(..., description="Micro-credits to add (negative to subtract)"),
    reason: str = Query(default="Admin adjustment"),
    admin: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Add or remove credits from a user."""
    await db.execute(text("""
        UPDATE users SET credit_balance = credit_balance + :amount, updated_at = NOW()
        WHERE id = :uid
    """), {"amount": amount, "uid": user_id})

    bal = await db.execute(text("SELECT credit_balance FROM users WHERE id = :uid"), {"uid": user_id})
    new_balance = bal.fetchone().credit_balance

    await db.execute(text("""
        INSERT INTO credit_transactions (user_id, amount, balance_after, transaction_type, description)
        VALUES (:uid, :amount, :balance, 'admin_adjustment', :reason)
    """), {"uid": user_id, "amount": amount, "balance": new_balance, "reason": reason})

    await db.commit()
    return {"new_balance": new_balance, "adjusted_by": amount}


@router.post("/admin/users/{user_id}/toggle")
async def admin_toggle_user(
    user_id: str,
    admin: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Enable or disable a user account."""
    result = await db.execute(text(
        "UPDATE users SET is_active = NOT is_active, updated_at = NOW() "
        "WHERE id = :uid RETURNING is_active"
    ), {"uid": user_id})
    row = result.fetchone()
    if not row:
        raise HTTPException(404, "User not found")
    await db.commit()
    return {"is_active": row.is_active}


# ============================================
# Circuit Breaker Status — Live Redis state
# ============================================

@router.get("/admin/providers/circuit-breaker")
async def admin_circuit_breaker(
    admin: dict = Depends(require_admin),
):
    """
    Live circuit breaker and health score status for every provider.

    Reads directly from Redis (not the DB), so this reflects the real-time
    routing decisions the gateway is making right now.

    Fields per provider:
      - circuit_state: "closed" | "open" | "half_open"
      - health_score:  0-100 (100 = fully healthy, 0 = all recent requests failed)
      - available:     whether the gateway will attempt this provider on new requests
    """
    states = await get_all_circuit_states(AUTO_ROUTE_ORDER)
    scores = await get_all_health_scores(AUTO_ROUTE_ORDER)

    providers = []
    for provider in AUTO_ROUTE_ORDER:
        state = states.get(provider, CircuitState.CLOSED)
        score = scores.get(provider, 100)
        providers.append({
            "provider":      provider,
            "circuit_state": state,
            "health_score":  score,
            "available":     state != CircuitState.OPEN,
            "status_label": (
                "🟢 Healthy"    if state == CircuitState.CLOSED  and score >= 80 else
                "🟡 Degraded"   if state == CircuitState.CLOSED  and score >= 50 else
                "🟠 Unhealthy"  if state == CircuitState.CLOSED  and score < 50  else
                "🔵 Probing"   if state == CircuitState.HALF_OPEN else
                "🔴 Open"
            ),
        })

    return {
        "providers": providers,
        "legend": {
            "closed":    "Normal — all requests flow through",
            "open":      "Tripped — requests skipped, provider resting",
            "half_open": "Probing — one test request allowed through",
        },
    }
