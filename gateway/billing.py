"""
Token metering and credit billing engine.

Uses micro-credits for precision:
  1 credit = 1,000,000 micro-credits
  This avoids floating-point errors in billing.
"""
import fnmatch
from typing import Optional

import tiktoken
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

# Cache the tokenizer
_encoding = tiktoken.get_encoding("cl100k_base")

# Cache model pricing (refreshed periodically)
_pricing_cache: list = []
_pricing_cache_time: float = 0


def count_tokens(text_content: str) -> int:
    """Count tokens in a string using tiktoken (cl100k_base encoding)."""
    if not text_content:
        return 0
    return len(_encoding.encode(text_content))

def count_message_tokens(messages: list) -> int:
    """Count tokens in a list of OpenAI-style messages."""
    total = 0
    for msg in messages:
        # Every message has role + content overhead (~4 tokens)
        total += 4
        content = msg.get("content", "")
        if isinstance(content, str):
            total += count_tokens(content)
        elif isinstance(content, list):
            # Multimodal: count text parts
            for part in content:
                if isinstance(part, dict) and part.get("type") == "text":
                    total += count_tokens(part.get("text", ""))
                elif isinstance(part, dict) and part.get("type") == "image_url":
                    total += 85  # rough estimate for image token cost
    total += 2  # assistant reply priming
    return total

def count_anthropic_tokens(body: dict) -> int:
    """Count tokens in an Anthropic-style request body."""
    # Anthropic uses 'messages' and optional 'system'
    messages = body.get("messages", [])
    system = body.get("system", "")
    
    total = 0
    if isinstance(system, str) and system:
        total += count_tokens(system) + 4
        
    for msg in messages:
        total += 4
        content = msg.get("content", "")
        if isinstance(content, str):
            total += count_tokens(content)
        elif isinstance(content, list):
            for part in content:
                if isinstance(part, dict) and part.get("type") == "text":
                    total += count_tokens(part.get("text", ""))
    return total


def count_gemini_tokens(body: dict) -> int:
    """Count tokens in a Gemini-style request body."""
    # Gemini uses 'contents' and optional 'systemInstruction'
    contents = body.get("contents", [])
    system = body.get("systemInstruction", {})
    
    total = 0
    # Process system instruction
    if system and isinstance(system, dict):
        parts = system.get("parts", [])
        for part in parts:
            if isinstance(part, dict) and "text" in part:
                total += count_tokens(part["text"])
    
    # Process contents
    for content in contents:
        parts = content.get("parts", [])
        for part in parts:
            if isinstance(part, dict) and "text" in part:
                total += count_tokens(part["text"])
            elif isinstance(part, dict) and ("inlineData" in part or "inline_data" in part):
                total += 100 # Rough estimate for image
                
    return total


async def get_model_pricing(db: AsyncSession, model: str, provider_type: str) -> dict:
    """
    Look up pricing for a model/provider combination.
    Returns dict with input_cost_per_million and output_cost_per_million (in micro-credits).
    """
    import time
    global _pricing_cache, _pricing_cache_time

    # Refresh cache every 60 seconds
    if time.time() - _pricing_cache_time > 60 or not _pricing_cache:
        result = await db.execute(text("""
            SELECT model_pattern, provider_type, input_cost_per_million, output_cost_per_million
            FROM model_pricing
            WHERE is_active = true
            ORDER BY priority DESC
        """))
        _pricing_cache = result.fetchall()
        _pricing_cache_time = time.time()

    # Find best matching pricing rule
    for row in _pricing_cache:
        pattern_match = fnmatch.fnmatch(model, row.model_pattern)
        provider_match = row.provider_type is None or row.provider_type == provider_type

        if pattern_match and provider_match:
            return {
                "input_cost_per_million": row.input_cost_per_million,
                "output_cost_per_million": row.output_cost_per_million,
            }

    # Fallback default
    return {
        "input_cost_per_million": 500000,   # $0.50 per 1M tokens
        "output_cost_per_million": 1000000, # $1.00 per 1M tokens
    }


def calculate_cost(
    input_tokens: int,
    output_tokens: int,
    pricing: dict,
) -> int:
    """
    Calculate cost in micro-credits.
    
    Args:
        input_tokens: Number of input/prompt tokens
        output_tokens: Number of output/completion tokens
        pricing: Dict with input_cost_per_million and output_cost_per_million
    
    Returns:
        Cost in micro-credits (integer)
    """
    input_cost = (input_tokens * pricing["input_cost_per_million"]) // 1_000_000
    output_cost = (output_tokens * pricing["output_cost_per_million"]) // 1_000_000
    return max(input_cost + output_cost, 1)  # minimum 1 micro-credit per request


async def check_and_deduct_credits(
    db: AsyncSession,
    user_id: str,
    estimated_cost: int,
) -> bool:
    """
    Atomically check balance and deduct credits.
    Returns True if successful, False if insufficient balance.
    """
    result = await db.execute(text("""
        UPDATE users 
        SET credit_balance = credit_balance - :cost,
            updated_at = NOW()
        WHERE id = :user_id 
          AND credit_balance >= :cost
          AND is_active = true
        RETURNING credit_balance
    """), {"cost": estimated_cost, "user_id": user_id})

    row = result.fetchone()
    if row is None:
        return False

    await db.commit()
    return True


async def refund_credits(
    db: AsyncSession,
    user_id: str,
    amount: int,
    reason: str = "overcharge_refund",
) -> None:
    """Refund credits to a user (e.g., if estimated cost was higher than actual)."""
    await db.execute(text("""
        UPDATE users 
        SET credit_balance = credit_balance + :amount,
            updated_at = NOW()
        WHERE id = :user_id
    """), {"amount": amount, "user_id": user_id})

    # Record the refund transaction
    await db.execute(text("""
        INSERT INTO credit_transactions (user_id, amount, balance_after, transaction_type, description)
        SELECT :user_id, :amount, credit_balance, 'refund', :reason
        FROM users WHERE id = :user_id
    """), {"user_id": user_id, "amount": amount, "reason": reason})

    await db.commit()


async def record_usage(
    db: AsyncSession,
    user_id: str,
    api_key_id: str,
    request_id: str,
    model_requested: str,
    model_used: str,
    provider_type: str,
    input_tokens: int,
    output_tokens: int,
    credits_charged: int,
    latency_ms: int,
    status: str = "success",
    error_message: Optional[str] = None,
    ip_address: Optional[str] = None,
) -> None:
    """Record a usage log entry and credit transaction."""
    # Handle master account by skipping DB insertion for now
    if user_id == "master":
        return
        
    total_tokens = input_tokens + output_tokens

    await db.execute(text("""
        INSERT INTO usage_logs (
            user_id, api_key_id, request_id, model_requested, model_used,
            provider_type, input_tokens, output_tokens, total_tokens,
            credits_charged, latency_ms, status, error_message, ip_address
        ) VALUES (
            :user_id, :api_key_id, :request_id, :model_requested, :model_used,
            :provider_type, :input_tokens, :output_tokens, :total_tokens,
            :credits_charged, :latency_ms, :status, :error_message, :ip_address
        )
    """), {
        "user_id": user_id,
        "api_key_id": api_key_id,
        "request_id": request_id,
        "model_requested": model_requested,
        "model_used": model_used,
        "provider_type": provider_type,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
        "credits_charged": credits_charged,
        "latency_ms": latency_ms,
        "status": status,
        "error_message": error_message,
        "ip_address": ip_address,
    })

    # Record credit deduction transaction
    if credits_charged > 0 and status == "success":
        await db.execute(text("""
            INSERT INTO credit_transactions (user_id, amount, balance_after, transaction_type, description, reference_id)
            SELECT :user_id, :amount, credit_balance, 'usage', :description, :request_id
            FROM users WHERE id = :user_id
        """), {
            "user_id": user_id,
            "amount": -credits_charged,
            "description": f"{model_used} | {input_tokens}in/{output_tokens}out tokens",
            "request_id": request_id,
        })

    await db.commit()
