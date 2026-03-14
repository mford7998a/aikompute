"""
Authentication: API key verification, JWT tokens, user management.
"""
import secrets
import hashlib
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import HTTPException, Security, Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
import bcrypt
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from database import get_db

security_scheme = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


def generate_api_key() -> tuple[str, str, str]:
    """Generate an API key. Returns (full_key, key_hash, key_prefix)."""
    raw = secrets.token_urlsafe(32)
    full_key = f"sk-inf-{raw}"
    key_hash = hashlib.sha256(full_key.encode()).hexdigest()
    key_prefix = full_key[:12]
    return full_key, key_hash, key_prefix


def create_jwt(user_id: str, email: str, is_admin: bool = False) -> str:
    """Create a JWT token for dashboard auth."""
    payload = {
        "sub": user_id,
        "email": email,
        "admin": is_admin,
        "exp": datetime.now(timezone.utc) + timedelta(hours=settings.JWT_EXPIRY_HOURS),
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_jwt(token: str) -> dict:
    """Decode and validate a JWT token."""
    try:
        return jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")


async def verify_api_key(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Security(security_scheme),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Verify an API key from the Authorization header.
    Returns user info dict with user_id, api_key_id, rate limits.
    """
    # Extract the key
    api_key = None
    if credentials:
        api_key = credentials.credentials
    if not api_key:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            api_key = auth_header[7:]

    if not api_key:
        raise HTTPException(status_code=401, detail="Missing API key. Use Authorization: Bearer sk-inf-...")

    # Check if it's the master key
    if api_key == settings.MASTER_API_KEY:
        return {
            "user_id": "master",
            "api_key_id": "master",
            "email": "admin@localhost",
            "is_admin": True,
            "rate_limit_rpm": 9999,
            "rate_limit_tpm": 99999999,
            "credit_balance": 999999999999,
        }

    # Hash and look up
    key_hash = hashlib.sha256(api_key.encode()).hexdigest()

    result = await db.execute(text("""
        SELECT 
            ak.id as api_key_id,
            ak.user_id,
            ak.rate_limit_rpm,
            ak.rate_limit_tpm,
            ak.is_active as key_active,
            u.email,
            u.credit_balance,
            u.is_active as user_active,
            u.is_admin
        FROM api_keys ak
        JOIN users u ON u.id = ak.user_id
        WHERE ak.key_hash = :key_hash
    """), {"key_hash": key_hash})

    row = result.fetchone()
    if not row:
        raise HTTPException(status_code=401, detail="Invalid API key")

    if not row.key_active:
        raise HTTPException(status_code=401, detail="API key has been deactivated")

    if not row.user_active:
        raise HTTPException(status_code=403, detail="Account has been suspended")

    # Update last_used timestamp (fire-and-forget)
    await db.execute(text("""
        UPDATE api_keys SET last_used_at = NOW() WHERE id = :key_id
    """), {"key_id": str(row.api_key_id)})
    await db.commit()

    return {
        "user_id": str(row.user_id),
        "api_key_id": str(row.api_key_id),
        "email": row.email,
        "is_admin": row.is_admin,
        "rate_limit_rpm": row.rate_limit_rpm,
        "rate_limit_tpm": row.rate_limit_tpm,
        "credit_balance": row.credit_balance,
    }


async def verify_jwt_token(
    credentials: HTTPAuthorizationCredentials = Security(security_scheme),
) -> dict:
    """Verify a JWT token from the Authorization header (for dashboard)."""
    if not credentials:
        raise HTTPException(status_code=401, detail="Missing authentication token")
    return decode_jwt(credentials.credentials)
