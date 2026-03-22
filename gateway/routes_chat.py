"""
API Routes: Chat completions endpoint (OpenAI-compatible).

This is the main endpoint users hit. It:
1. Verifies the API key
2. Checks rate limits
3. Checks credit balance
4. Forwards to AIClient-2-API (which handles protocol transformation + account rotation)
5. Meters token usage
6. Charges credits

Session stickiness: pass X-Session-ID header to keep a multi-turn conversation
on the same upstream provider for 60 seconds.
"""
import time
import uuid
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from auth import verify_api_key
from billing import (
    count_message_tokens,
    count_tokens,
    count_anthropic_tokens,
    count_gemini_tokens,
    get_model_pricing,
    calculate_cost,
    check_and_deduct_credits,
    refund_credits,
    record_usage,
)
from database import get_db
from proxy import proxy, resolve_provider, resolve_fallback_providers, AUTO_ROUTE_ORDER
from rate_limiter import check_rate_limit, record_token_usage

router = APIRouter()


# ============================================
# Request / Response Models
# ============================================

class ChatMessage(BaseModel):
    role: str
    content: str | list

class ChatCompletionRequest(BaseModel):
    model: str = "auto"
    messages: List[ChatMessage]
    temperature: Optional[float] = 0.7
    max_tokens: Optional[int] = None
    stream: Optional[bool] = False
    top_p: Optional[float] = None
    frequency_penalty: Optional[float] = None
    presence_penalty: Optional[float] = None
    stop: Optional[list] = None

class ModelInfo(BaseModel):
    id: str
    object: str = "model"
    owned_by: str = "inference-gateway"

class ModelListResponse(BaseModel):
    object: str = "list"
    data: List[ModelInfo]


# ============================================
# /v1/chat/completions — Main inference endpoint
# ============================================

@router.post("/v1/chat/completions")
async def chat_completions(
    request: ChatCompletionRequest,
    raw_request: Request,
    user: dict = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
):
    """
    OpenAI-compatible chat completions endpoint.
    
    Accepts standard OpenAI request format.
    Routes through AIClient-2-API which transforms the request
    into the appropriate provider protocol (Gemini CLI, Kiro, etc.).
    """
    request_id = f"chatcmpl-{uuid.uuid4().hex[:24]}"
    start_time = time.monotonic()
    client_ip = raw_request.client.host if raw_request.client else None

    # -- Session ID for stickiness (X-Session-ID header, or synthesize one) --
    session_id = (
        raw_request.headers.get("x-session-id")
        or raw_request.headers.get("X-Session-ID")
        or ""
    )

    # -- 1. Estimate input tokens for rate limiting and pre-charge --
    messages_dicts = [m.model_dump() for m in request.messages]
    estimated_input_tokens = count_message_tokens(messages_dicts)

    # -- 2. Rate limiting --
    await check_rate_limit(
        user_id=user["user_id"],
        api_key_id=user["api_key_id"],
        rpm_limit=user["rate_limit_rpm"],
        tpm_limit=user["rate_limit_tpm"],
        estimated_tokens=estimated_input_tokens,
    )

    # -- 3. Resolve provider --
    if request.model == "auto":
        provider_type = AUTO_ROUTE_ORDER[0]
        providers_to_try = AUTO_ROUTE_ORDER
    else:
        provider_type = resolve_provider(request.model)
        # Only fallback to providers that can serve the SAME model
        providers_to_try = resolve_fallback_providers(request.model)

    # -- 4. Pre-charge estimate (to prevent usage without payment) --
    estimated_output = request.max_tokens or 1000
    pricing = await get_model_pricing(db, request.model, provider_type)
    estimated_cost = calculate_cost(estimated_input_tokens, estimated_output, pricing)

    # Check balance (skip for master/admin)
    if user["user_id"] != "master":
        if user["credit_balance"] < estimated_cost:
            raise HTTPException(
                status_code=402,
                detail={
                    "error": "insufficient_credits",
                    "message": f"Insufficient credits. Estimated cost: {estimated_cost} micro-credits, balance: {user['credit_balance']}",
                    "credits_needed": estimated_cost,
                    "credits_available": user["credit_balance"],
                }
            )

    # -- 5. Handle streaming vs non-streaming --
    if request.stream:
        return await _handle_streaming(
            request, messages_dicts, providers_to_try, provider_type,
            pricing, estimated_input_tokens, request_id, start_time,
            user, db, client_ip, session_id,
        )
    else:
        return await _handle_non_streaming(
            request, messages_dicts, providers_to_try, provider_type,
            pricing, estimated_input_tokens, request_id, start_time,
            user, db, client_ip, session_id,
        )


async def _handle_non_streaming(
    request, messages_dicts, providers_to_try, provider_type,
    pricing, estimated_input_tokens, request_id, start_time,
    user, db, client_ip, session_id: str = "",
):
    """Handle a non-streaming chat completion request."""
    try:
        response = await proxy.try_with_fallback(
            model=request.model,
            messages=messages_dicts,
            providers_to_try=providers_to_try,
            session_id=session_id,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            top_p=request.top_p,
            frequency_penalty=request.frequency_penalty,
            presence_penalty=request.presence_penalty,
            stop=request.stop,
        )
    except HTTPException as e:
        # Record failed request
        elapsed_ms = int((time.monotonic() - start_time) * 1000)
        if user["user_id"] != "master":
            await record_usage(
                db=db, user_id=user["user_id"], api_key_id=user["api_key_id"],
                request_id=request_id, model_requested=request.model,
                model_used=request.model, provider_type=provider_type,
                input_tokens=estimated_input_tokens, output_tokens=0,
                credits_charged=0, latency_ms=elapsed_ms,
                status="error", error_message=str(e.detail), ip_address=client_ip,
            )
        raise

    # Extract actual usage from response
    usage = response.get("usage", {})
    actual_input = usage.get("prompt_tokens", estimated_input_tokens)
    actual_output = usage.get("completion_tokens", 0)

    # If AIClient-2-API didn't return usage, count from response text
    if actual_output == 0:
        choices = response.get("choices", [])
        if choices:
            content = choices[0].get("message", {}).get("content", "")
            actual_output = count_tokens(content)

    actual_provider = response.pop("_provider_type", provider_type)
    latency_ms = response.pop("_latency_ms", int((time.monotonic() - start_time) * 1000))

    # Calculate actual cost
    actual_pricing = await get_model_pricing(db, request.model, actual_provider)
    actual_cost = calculate_cost(actual_input, actual_output, actual_pricing)

    # Charge credits
    if user["user_id"] != "master":
        success = await check_and_deduct_credits(db, user["user_id"], actual_cost)
        if not success:
            raise HTTPException(status_code=402, detail="Insufficient credits for this request")

    # Record usage
    await record_usage(
        db=db, user_id=user["user_id"], api_key_id=user["api_key_id"],
        request_id=request_id, model_requested=request.model,
        model_used=response.get("model", request.model),
        provider_type=actual_provider,
        input_tokens=actual_input, output_tokens=actual_output,
        credits_charged=actual_cost, latency_ms=latency_ms,
        status="success", ip_address=client_ip,
    )

    # Record tokens for TPM rate limiting
    await record_token_usage(user["api_key_id"], actual_input + actual_output)

    # Ensure consistent response format
    response["id"] = request_id
    if "usage" not in response:
        response["usage"] = {
            "prompt_tokens": actual_input,
            "completion_tokens": actual_output,
            "total_tokens": actual_input + actual_output,
        }

    return response


async def _handle_streaming(
    request, messages_dicts, providers_to_try, provider_type,
    pricing, estimated_input_tokens, request_id, start_time,
    user, db, client_ip, session_id: str = "",
):
    """Handle a streaming chat completion request."""

    async def stream_with_billing():
        accumulated_text = ""
        last_error = ""
        success = False

        try:
            for provider in providers_to_try:
                try:
                    async for chunk in proxy.chat_completion_stream(
                        model=request.model,
                        messages=messages_dicts,
                        provider_type=provider,
                        temperature=request.temperature,
                        max_tokens=request.max_tokens,
                        top_p=request.top_p,
                        frequency_penalty=request.frequency_penalty,
                        presence_penalty=request.presence_penalty,
                        stop=request.stop,
                    ):
                        # Accumulate text for post-stream billing
                        if chunk.startswith("data: ") and chunk.strip() != "data: [DONE]":
                            try:
                                import json
                                data = json.loads(chunk[6:])
                                choices = data.get("choices", [])
                                if choices:
                                    delta = choices[0].get("delta", {})
                                    content = delta.get("content", "")
                                    if content:
                                        accumulated_text += content
                            except (json.JSONDecodeError, KeyError):
                                pass

                        yield chunk

                    success = True
                    break  # Provider worked, exit the loop

                except Exception as e:
                    last_error = str(e)
                    continue  # Try next provider

            if not success:
                safe_err = last_error.replace('"', "'")
                yield f'data: {{"error": {{"message": "All providers failed. Last error: {safe_err}"}}}}\n\n'
                yield "data: [DONE]\n\n"

        finally:
            # Bill after stream completes
            actual_output = count_tokens(accumulated_text)
            latency_ms = int((time.monotonic() - start_time) * 1000)

            actual_pricing = await get_model_pricing(db, request.model, provider_type)
            actual_cost = calculate_cost(estimated_input_tokens, actual_output, actual_pricing)

            if user["user_id"] != "master":
                await check_and_deduct_credits(db, user["user_id"], actual_cost)

            await record_usage(
                db=db, user_id=user["user_id"], api_key_id=user["api_key_id"],
                request_id=request_id, model_requested=request.model,
                model_used=request.model, provider_type=provider_type,
                input_tokens=estimated_input_tokens, output_tokens=actual_output,
                credits_charged=actual_cost, latency_ms=latency_ms,
                status="success", ip_address=client_ip,
            )

            await record_token_usage(user["api_key_id"], estimated_input_tokens + actual_output)

    return StreamingResponse(
        stream_with_billing(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Request-ID": request_id,
        },
    )


# ============================================
# Anthropic /v1/messages — Claude native format
# ============================================

@router.post("/v1/messages")
async def anthropic_messages(
    raw_request: Request,
    user: dict = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
):
    """Anthropic-compatible messages endpoint."""
    body = await raw_request.json()
    model = body.get("model", "claude-sonnet-4-5")
    stream = body.get("stream", False)
    request_id = f"msg-{uuid.uuid4().hex[:24]}"
    start_time = time.monotonic()
    client_ip = raw_request.client.host if raw_request.client else None

    # -- 1. Billing --
    estimated_input_tokens = count_anthropic_tokens(body)
    provider_type = resolve_provider(model)
    pricing = await get_model_pricing(db, model, provider_type)
    
    # Pre-charge check
    estimated_cost = calculate_cost(estimated_input_tokens, 1000, pricing)
    if user["user_id"] != "master" and user["credit_balance"] < estimated_cost:
        raise HTTPException(status_code=402, detail="Insufficient credits")

    # -- 2. Proxy --
    if stream:
        async def anthropic_stream():
            accumulated_text = ""
            async for chunk in proxy.generic_proxy_stream("/v1/messages", body, provider_type):
                yield chunk
            
            # Post-stream billing
            actual_output = count_tokens(proxy._last_stream_text)
            actual_cost = calculate_cost(estimated_input_tokens, actual_output, pricing)
            if user["user_id"] != "master":
                await check_and_deduct_credits(db, user["user_id"], actual_cost)
            await record_usage(
                db=db, user_id=user["user_id"], api_key_id=user["api_key_id"],
                request_id=request_id, model_requested=model,
                model_used=model, provider_type=provider_type,
                input_tokens=estimated_input_tokens, output_tokens=actual_output,
                credits_charged=actual_cost, latency_ms=int((time.monotonic() - start_time) * 1000),
                status="success", ip_address=client_ip,
            )

        return StreamingResponse(anthropic_stream(), media_type="text/event-stream")
    else:
        response = await proxy.generic_proxy("/v1/messages", body, provider_type)
        actual_output = response.get("usage", {}).get("output_tokens", 0)
        actual_cost = calculate_cost(estimated_input_tokens, actual_output, pricing)
        
        if user["user_id"] != "master":
            await check_and_deduct_credits(db, user["user_id"], actual_cost)
        
        await record_usage(
            db=db, user_id=user["user_id"], api_key_id=user["api_key_id"],
            request_id=request_id, model_requested=model,
            model_used=model, provider_type=provider_type,
            input_tokens=estimated_input_tokens, output_tokens=actual_output,
            credits_charged=actual_cost, latency_ms=response.get("_latency_ms", 0),
            status="success", ip_address=client_ip,
        )
        return response


# ============================================
# Gemini /v1beta/models — Gemini native format
# ============================================

@router.post("/v1beta/models/{model}:generateContent")
@router.post("/v1beta/models/{model}:streamGenerateContent")
async def gemini_generate_content(
    model: str,
    raw_request: Request,
    user: dict = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
):
    """Gemini-compatible generateContent endpoint."""
    body = await raw_request.json()
    path = raw_request.url.path
    is_stream = "streamGenerateContent" in path
    request_id = f"gem-{uuid.uuid4().hex[:24]}"
    start_time = time.monotonic()
    client_ip = raw_request.client.host if raw_request.client else None

    # -- 1. Billing --
    estimated_input_tokens = count_gemini_tokens(body)
    provider_type = resolve_provider(model)
    pricing = await get_model_pricing(db, model, provider_type)
    
    # Pre-charge check
    estimated_cost = calculate_cost(estimated_input_tokens, 1000, pricing)
    if user["user_id"] != "master" and user["credit_balance"] < estimated_cost:
        raise HTTPException(status_code=402, detail="Insufficient credits")

    # -- 2. Proxy --
    if is_stream:
        async def gemini_stream():
            async for chunk in proxy.generic_proxy_stream(path, body, provider_type):
                yield chunk
            
            # Post-stream billing
            actual_output = count_tokens(proxy._last_stream_text)
            actual_cost = calculate_cost(estimated_input_tokens, actual_output, pricing)
            if user["user_id"] != "master":
                await check_and_deduct_credits(db, user["user_id"], actual_cost)
            await record_usage(
                db=db, user_id=user["user_id"], api_key_id=user["api_key_id"],
                request_id=request_id, model_requested=model,
                model_used=model, provider_type=provider_type,
                input_tokens=estimated_input_tokens, output_tokens=actual_output,
                credits_charged=actual_cost, latency_ms=int((time.monotonic() - start_time) * 1000),
                status="success", ip_address=client_ip,
            )

        return StreamingResponse(gemini_stream(), media_type="text/event-stream")
    else:
        response = await proxy.generic_proxy(path, body, provider_type)
        # Extract Gemini usage
        usage = response.get("usageMetadata", {})
        actual_output = usage.get("candidatesTokenCount", 0)
        actual_cost = calculate_cost(estimated_input_tokens, actual_output, pricing)
        
        if user["user_id"] != "master":
            await check_and_deduct_credits(db, user["user_id"], actual_cost)
        
        await record_usage(
            db=db, user_id=user["user_id"], api_key_id=user["api_key_id"],
            request_id=request_id, model_requested=model,
            model_used=model, provider_type=provider_type,
            input_tokens=estimated_input_tokens, output_tokens=actual_output,
            credits_charged=actual_cost, latency_ms=response.get("_latency_ms", 0),
            status="success", ip_address=client_ip,
        )
        return response


# ============================================
# /v1/models — List available models
# ============================================

@router.get("/v1/models")
async def list_models(user: dict = Depends(verify_api_key)):
    """List available models through this gateway."""
    models = [
        # ── Antigravity / Gemini ──────────────────────────────────────────
        {"id": "gemini-2.0-flash",     "object": "model", "owned_by": "inference-gateway"},
        {"id": "gemini-2.5-pro",       "object": "model", "owned_by": "inference-gateway"},
        {"id": "gemini-3.0-pro",       "object": "model", "owned_by": "inference-gateway"},
        {"id": "gemini-3.0-flash",     "object": "model", "owned_by": "inference-gateway"},
        {"id": "gemini-3.1-pro-high",  "object": "model", "owned_by": "inference-gateway"},
        {"id": "gemini-3.1-pro-low",   "object": "model", "owned_by": "inference-gateway"},
        # ── Kiro / Claude ────────────────────────────────────────────────
        {"id": "claude-sonnet-4-6",    "object": "model", "owned_by": "inference-gateway"},
        {"id": "claude-opus-4-6",      "object": "model", "owned_by": "inference-gateway"},
        {"id": "claude-sonnet-4-5",    "object": "model", "owned_by": "inference-gateway"},
        {"id": "claude-opus-4-5",      "object": "model", "owned_by": "inference-gateway"},
        {"id": "claude-sonnet-4",      "object": "model", "owned_by": "inference-gateway"},
        {"id": "claude-opus-4",        "object": "model", "owned_by": "inference-gateway"},
        {"id": "claude-haiku-3-5",     "object": "model", "owned_by": "inference-gateway"},
        {"id": "kiro-claude-opus-4-5-thinking", "object": "model", "owned_by": "inference-gateway"},
        {"id": "kiro-claude-sonnet-4-5", "object": "model", "owned_by": "inference-gateway"},
        # ── Qwen ─────────────────────────────────────────────────────────
        {"id": "qwen3-coder-plus",     "object": "model", "owned_by": "inference-gateway"},
        # ── iFlow (paid) ──────────────────────────────────────────────────
        {"id": "gpt-4o",               "object": "model", "owned_by": "inference-gateway"},
        {"id": "deepseek-v3",          "object": "model", "owned_by": "inference-gateway"},
        {"id": "deepseek-r1",          "object": "model", "owned_by": "inference-gateway"},
        # ── GitHub Models (free via GitHub PAT) ───────────────────────────
        {"id": "github-gpt-4o",        "object": "model", "owned_by": "github"},
        {"id": "github-gpt-4.1",       "object": "model", "owned_by": "github"},
        {"id": "github-o4-mini",       "object": "model", "owned_by": "github"},
        {"id": "github-claude-sonnet", "object": "model", "owned_by": "github"},
        {"id": "github-gemini-pro",    "object": "model", "owned_by": "github"},
        {"id": "github-deepseek-v3",   "object": "model", "owned_by": "github"},
        # ── GitHub Copilot (free/pro/enterprise via OAuth) ──────────────────
        {"id": "copilot-gpt-4o",        "object": "model", "owned_by": "github-copilot"},
        {"id": "copilot-gpt-4.1",       "object": "model", "owned_by": "github-copilot"},
        {"id": "copilot-o4-mini",       "object": "model", "owned_by": "github-copilot"},
        {"id": "copilot-claude-sonnet", "object": "model", "owned_by": "github-copilot"},
        {"id": "copilot-claude-haiku",  "object": "model", "owned_by": "github-copilot"},
        # ── OpenRouter (free tier) ───────────────────────────────────────
        {"id": "or-gemma-3-27b",        "object": "model", "owned_by": "openrouter"},
        {"id": "or-gemma-3-12b",        "object": "model", "owned_by": "openrouter"},
        {"id": "or-gemma-3-4b",         "object": "model", "owned_by": "openrouter"},
        {"id": "or-gemma-3n-e4b",       "object": "model", "owned_by": "openrouter"},
        {"id": "or-gemma-3n-e2b",       "object": "model", "owned_by": "openrouter"},
        {"id": "or-llama-3.3-70b",      "object": "model", "owned_by": "openrouter"},
        {"id": "or-llama-3.2-3b",       "object": "model", "owned_by": "openrouter"},
        {"id": "or-hermes-3-405b",      "object": "model", "owned_by": "openrouter"},
        {"id": "or-mistral-small-3.1",  "object": "model", "owned_by": "openrouter"},
        {"id": "or-qwen3-4b",           "object": "model", "owned_by": "openrouter"},
        {"id": "or-nemotron-3-super",   "object": "model", "owned_by": "openrouter"},
        {"id": "or-nemotron-3-nano",    "object": "model", "owned_by": "openrouter"},
        {"id": "or-minimax-m2.5",       "object": "model", "owned_by": "openrouter"},
        {"id": "or-step-3.5-flash",     "object": "model", "owned_by": "openrouter"},
        {"id": "or-trinity-large",      "object": "model", "owned_by": "openrouter"},
        {"id": "or-trinity-mini",       "object": "model", "owned_by": "openrouter"},
        {"id": "or-glm-4.5-air",        "object": "model", "owned_by": "openrouter"},
        {"id": "or-lfm-2.5-thinking",   "object": "model", "owned_by": "openrouter"},
        {"id": "or-lfm-2.5-instruct",   "object": "model", "owned_by": "openrouter"},
        # ── WebAI (browser-based) ─────────────────────────────────────────

        # ── Routing alias ─────────────────────────────────────────────────
        {"id": "auto",                 "object": "model", "owned_by": "inference-gateway"},
    ]
    return {"object": "list", "data": models}
