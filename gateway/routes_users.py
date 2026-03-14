"""
API Routes: User management, API keys, billing, and dashboard endpoints.
"""
import hashlib
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from auth import (
    hash_password, verify_password, generate_api_key,
    create_jwt, verify_api_key, verify_jwt_token,
)
from config import settings
from database import get_db

router = APIRouter()


# ============================================
# Auth / Registration
# ============================================

class RegisterRequest(BaseModel):
    email: str
    password: str
    display_name: Optional[str] = None

class LoginRequest(BaseModel):
    email: str
    password: str


@router.post("/auth/register")
async def register(req: RegisterRequest, db: AsyncSession = Depends(get_db)):
    """Register a new user account."""
    # Check if email already exists
    existing = await db.execute(
        text("SELECT id FROM users WHERE email = :email"),
        {"email": req.email},
    )
    if existing.fetchone():
        raise HTTPException(400, "Email already registered")

    pwd_hash = hash_password(req.password)
    full_key, key_hash, key_prefix = generate_api_key()

    # Create user
    result = await db.execute(text("""
        INSERT INTO users (email, password_hash, display_name, credit_balance)
        VALUES (:email, :pwd_hash, :display_name, :free_credits)
        RETURNING id, email, credit_balance
    """), {
        "email": req.email,
        "pwd_hash": pwd_hash,
        "display_name": req.display_name or req.email.split("@")[0],
        "free_credits": settings.NEW_USER_FREE_CREDITS,
    })
    user = result.fetchone()

    # Create default API key
    await db.execute(text("""
        INSERT INTO api_keys (user_id, key_hash, key_prefix, name)
        VALUES (:user_id, :key_hash, :key_prefix, 'Default Key')
    """), {
        "user_id": str(user.id),
        "key_hash": key_hash,
        "key_prefix": key_prefix,
    })

    # Record free credits transaction
    await db.execute(text("""
        INSERT INTO credit_transactions (user_id, amount, balance_after, transaction_type, description)
        VALUES (:user_id, :amount, :balance, 'bonus', 'Welcome bonus credits')
    """), {
        "user_id": str(user.id),
        "amount": settings.NEW_USER_FREE_CREDITS,
        "balance": settings.NEW_USER_FREE_CREDITS,
    })

    await db.commit()

    token = create_jwt(str(user.id), user.email)

    return {
        "user_id": str(user.id),
        "email": user.email,
        "api_key": full_key,
        "credit_balance": user.credit_balance,
        "jwt_token": token,
        "message": "Account created! Save your API key — it won't be shown again.",
    }


@router.post("/auth/login")
async def login(req: LoginRequest, db: AsyncSession = Depends(get_db)):
    """Login and get a JWT token for the dashboard."""
    result = await db.execute(text("""
        SELECT id, email, password_hash, is_admin, credit_balance, is_active
        FROM users WHERE email = :email
    """), {"email": req.email})
    user = result.fetchone()

    if not user or not verify_password(req.password, user.password_hash):
        raise HTTPException(401, "Invalid email or password")

    if not user.is_active:
        raise HTTPException(403, "Account has been suspended")

    token = create_jwt(str(user.id), user.email, user.is_admin)

    return {
        "jwt_token": token,
        "user_id": str(user.id),
        "email": user.email,
        "is_admin": user.is_admin,
        "credit_balance": user.credit_balance,
    }


# ============================================
# API Key Management
# ============================================

class CreateKeyRequest(BaseModel):
    name: str = "New Key"


@router.get("/user/keys")
async def list_api_keys(
    jwt: dict = Depends(verify_jwt_token),
    db: AsyncSession = Depends(get_db),
):
    """List all API keys for the authenticated user."""
    result = await db.execute(text("""
        SELECT id, key_prefix, name, is_active, rate_limit_rpm, rate_limit_tpm, last_used_at, created_at
        FROM api_keys WHERE user_id = :user_id ORDER BY created_at DESC
    """), {"user_id": jwt["sub"]})

    keys = [dict(row._mapping) for row in result.fetchall()]
    # Convert UUIDs and timestamps to strings
    for key in keys:
        key["id"] = str(key["id"])
        key["last_used_at"] = str(key["last_used_at"]) if key["last_used_at"] else None
        key["created_at"] = str(key["created_at"])

    return {"keys": keys}


@router.post("/user/keys")
async def create_api_key(
    req: CreateKeyRequest,
    jwt: dict = Depends(verify_jwt_token),
    db: AsyncSession = Depends(get_db),
):
    """Generate a new API key."""
    full_key, key_hash, key_prefix = generate_api_key()

    await db.execute(text("""
        INSERT INTO api_keys (user_id, key_hash, key_prefix, name)
        VALUES (:user_id, :key_hash, :key_prefix, :name)
    """), {
        "user_id": jwt["sub"],
        "key_hash": key_hash,
        "key_prefix": key_prefix,
        "name": req.name,
    })
    await db.commit()

    return {
        "api_key": full_key,
        "key_prefix": key_prefix,
        "name": req.name,
        "message": "Save this key — it won't be shown again.",
    }


@router.delete("/user/keys/{key_id}")
async def revoke_api_key(
    key_id: str,
    jwt: dict = Depends(verify_jwt_token),
    db: AsyncSession = Depends(get_db),
):
    """Revoke (deactivate) an API key."""
    result = await db.execute(text("""
        UPDATE api_keys SET is_active = false
        WHERE id = :key_id AND user_id = :user_id
        RETURNING id
    """), {"key_id": key_id, "user_id": jwt["sub"]})

    if not result.fetchone():
        raise HTTPException(404, "Key not found")

    await db.commit()
    return {"message": "Key revoked"}


# ============================================
# Usage & Billing
# ============================================

@router.get("/user/usage")
async def get_usage(
    days: int = 30,
    jwt: dict = Depends(verify_jwt_token),
    db: AsyncSession = Depends(get_db),
):
    """Get usage statistics for the authenticated user."""
    # Per-model summary
    result = await db.execute(text("""
        SELECT 
            model_used as model,
            provider_type as provider,
            COUNT(*) as request_count,
            SUM(input_tokens) as total_input_tokens,
            SUM(output_tokens) as total_output_tokens,
            SUM(total_tokens) as total_tokens,
            SUM(credits_charged) as total_credits,
            AVG(latency_ms)::int as avg_latency_ms
        FROM usage_logs
        WHERE user_id = :user_id 
          AND created_at > NOW() - make_interval(days => :days)
          AND status = 'success'
        GROUP BY model_used, provider_type
        ORDER BY total_credits DESC
    """), {"user_id": jwt["sub"], "days": days})

    summary = [dict(row._mapping) for row in result.fetchall()]

    # Daily breakdown
    daily = await db.execute(text("""
        SELECT 
            DATE(created_at) as date,
            COUNT(*) as requests,
            SUM(total_tokens) as tokens,
            SUM(credits_charged) as credits
        FROM usage_logs
        WHERE user_id = :user_id 
          AND created_at > NOW() - make_interval(days => :days)
          AND status = 'success'
        GROUP BY DATE(created_at)
        ORDER BY date DESC
    """), {"user_id": jwt["sub"], "days": days})

    daily_data = [dict(row._mapping) for row in daily.fetchall()]
    for d in daily_data:
        d["date"] = str(d["date"])

    return {"summary": summary, "daily": daily_data}


@router.get("/user/balance")
async def get_balance(
    jwt: dict = Depends(verify_jwt_token),
    db: AsyncSession = Depends(get_db),
):
    """Get current credit balance."""
    result = await db.execute(text("""
        SELECT credit_balance, email, display_name FROM users WHERE id = :user_id
    """), {"user_id": jwt["sub"]})
    user = result.fetchone()
    if not user:
        raise HTTPException(404, "User not found")

    return {
        "credit_balance": user.credit_balance,
        "credits_display": f"{user.credit_balance / 1_000_000:.2f}",
        "email": user.email,
        "display_name": user.display_name,
    }


@router.get("/user/transactions")
async def get_transactions(
    limit: int = 50,
    offset: int = 0,
    jwt: dict = Depends(verify_jwt_token),
    db: AsyncSession = Depends(get_db),
):
    """Get credit transaction history."""
    result = await db.execute(text("""
        SELECT id, amount, balance_after, transaction_type, description, created_at
        FROM credit_transactions
        WHERE user_id = :user_id
        ORDER BY created_at DESC
        LIMIT :limit OFFSET :offset
    """), {"user_id": jwt["sub"], "limit": limit, "offset": offset})

    transactions = [dict(row._mapping) for row in result.fetchall()]
    for t in transactions:
        t["id"] = str(t["id"])
        t["created_at"] = str(t["created_at"])

    return {"transactions": transactions}


# ============================================
# Credit Packages
# ============================================

@router.get("/billing/packages")
async def list_packages(db: AsyncSession = Depends(get_db)):
    """List available credit packages for purchase."""
    result = await db.execute(text("""
        SELECT id, name, credits, price_cents
        FROM credit_packages
        WHERE is_active = true
        ORDER BY sort_order
    """))

    packages = []
    for row in result.fetchall():
        packages.append({
            "id": str(row.id),
            "name": row.name,
            "credits": row.credits,
            "credits_display": f"{row.credits / 1_000_000:.0f}",
            "price_usd": f"${row.price_cents / 100:.2f}",
            "price_cents": row.price_cents,
        })

    return {"packages": packages}


@router.post("/billing/purchase/{package_id}")
async def purchase_credits(
    package_id: str,
    jwt: dict = Depends(verify_jwt_token),
    db: AsyncSession = Depends(get_db),
):
    """
    Purchase credits. 
    In production, this creates a Stripe checkout session.
    For now, it directly adds credits (for testing).
    """
    # Look up package
    result = await db.execute(text("""
        SELECT id, name, credits, price_cents 
        FROM credit_packages WHERE id = :id AND is_active = true
    """), {"id": package_id})
    pkg = result.fetchone()
    if not pkg:
        raise HTTPException(404, "Package not found")

    # TODO: In production, create Stripe checkout session here
    # For now, directly add credits (simulating payment)

    await db.execute(text("""
        UPDATE users SET credit_balance = credit_balance + :credits, updated_at = NOW()
        WHERE id = :user_id
    """), {"credits": pkg.credits, "user_id": jwt["sub"]})

    # Get new balance
    bal = await db.execute(text("SELECT credit_balance FROM users WHERE id = :uid"), {"uid": jwt["sub"]})
    new_balance = bal.fetchone().credit_balance

    await db.execute(text("""
        INSERT INTO credit_transactions (user_id, amount, balance_after, transaction_type, description)
        VALUES (:user_id, :amount, :balance, 'purchase', :desc)
    """), {
        "user_id": jwt["sub"],
        "amount": pkg.credits,
        "balance": new_balance,
        "desc": f"Purchased {pkg.name} package (${pkg.price_cents/100:.2f})",
    })

    await db.commit()

    return {
        "message": f"Successfully purchased {pkg.name}",
        "credits_added": pkg.credits,
        "new_balance": new_balance,
        "new_balance_display": f"{new_balance / 1_000_000:.2f}",
    }


# ============================================
# Model Pricing (public)
# ============================================

@router.get("/pricing")
async def get_pricing(db: AsyncSession = Depends(get_db)):
    """Get current model pricing."""
    result = await db.execute(text("""
        SELECT model_pattern, provider_type, input_cost_per_million, output_cost_per_million
        FROM model_pricing WHERE is_active = true ORDER BY priority DESC
    """))

    pricing = []
    for row in result.fetchall():
        pricing.append({
            "model": row.model_pattern,
            "provider": row.provider_type or "any",
            "input_per_million_credits": f"{row.input_cost_per_million / 1_000_000:.4f}",
            "output_per_million_credits": f"{row.output_cost_per_million / 1_000_000:.4f}",
        })

    return {"pricing": pricing}
