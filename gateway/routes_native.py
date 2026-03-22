from fastapi import APIRouter, Depends, HTTPException, Request, BackgroundTasks
from fastapi.responses import StreamingResponse
from typing import Optional
import time
import uuid
import json
import httpx

from auth import verify_api_key
from billing import (
    count_anthropic_tokens,
    count_gemini_tokens,
    get_model_pricing,
    calculate_cost,
    record_usage,
    count_tokens
)
from database import get_db, async_session_factory
from sqlalchemy import text
from proxy import proxy, resolve_provider, resolve_fallback_providers

router = APIRouter()


async def bill_after_stream(
    user_id, api_key_id, request_id, 
    model, provider_type, input_tokens, 
    accumulated_text, elapsed_ms, client_ip
):
    """
    Background task to handle billing after the stream has finished.
    Creates its own database session to avoid 'already closed' errors.
    """
    output_tokens = count_tokens(accumulated_text)
    async with async_session_factory() as db:
        try:
            pricing = await get_model_pricing(db, model, provider_type)
            cost = calculate_cost(input_tokens, output_tokens, pricing)

            if user_id != "master":
                await db.execute(
                    text("UPDATE users SET credit_balance = credit_balance - :cost WHERE id = :user_id AND credit_balance >= :cost"),
                    {"cost": cost, "user_id": user_id}
                )
                await db.commit()

            await record_usage(
                db=db, user_id=user_id, api_key_id=api_key_id,
                request_id=request_id, model_requested=model, model_used=model,
                provider_type=provider_type, input_tokens=input_tokens,
                output_tokens=output_tokens,
                credits_charged=cost if user_id != "master" else 0,
                latency_ms=elapsed_ms, status="success", error_message=None,
                ip_address=client_ip,
            )
        except Exception as e:
            # We log failed billing in production logs but never crash the gateway
            print(f"Billing Error: {e}")


async def _transparent_stream(
    upstream_response, start_time, user, background_tasks, request_id, 
    model, provider_type, input_tokens, client_ip, vendor
):
    """
    Transparently pass raw SSE bytes from upstream while sniffing content.
    """
    accumulated_text = ""
    buffer = ""

    try:
        async for raw_bytes in upstream_response.aiter_bytes():
            yield raw_bytes

            # Decode and sniff for billing
            try:
                buffer += raw_bytes.decode("utf-8", errors="replace")
                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    line = line.strip()
                    if not line or not line.startswith("data:"):
                        continue
                    data_str = line[5:].strip()
                    if data_str == "[DONE]":
                        continue
                    try:
                        data = json.loads(data_str)
                        if vendor == "anthropic":
                            if data.get("type") == "content_block_delta":
                                delta = data.get("delta", {})
                                accumulated_text += delta.get("text", "")
                        elif vendor == "gemini":
                            candidates = data.get("candidates", [])
                            if candidates:
                                parts = candidates[0].get("content", {}).get("parts", [])
                                for p in parts:
                                    accumulated_text += p.get("text", "")
                    except (json.JSONDecodeError, KeyError):
                        pass
            except Exception:
                pass
    finally:
        # 1. Close upstream connection
        await upstream_response.aclose()
        # 2. Schedule billing in background to avoid blocking the user
        elapsed_ms = int((time.monotonic() - start_time) * 1000)
        background_tasks.add_task(
            bill_after_stream,
            user["user_id"], user["api_key_id"], request_id,
            model, provider_type, input_tokens,
            accumulated_text, elapsed_ms, client_ip
        )


@router.post("/v1/messages")
async def anthropic_messages(
    raw_request: Request,
    background_tasks: BackgroundTasks,
    user: dict = Depends(verify_api_key),
    db=Depends(get_db),
):
    """Native Anthropic /v1/messages passthrough with billing."""
    body = await raw_request.json()
    model = body.get("model", "")
    if not model:
        raise HTTPException(status_code=400, detail="model is required")

    client_ip = raw_request.client.host if raw_request.client else None
    request_id = f"msg_{uuid.uuid4().hex[:24]}"
    start_time = time.monotonic()

    input_tokens = count_anthropic_tokens(body)
    provider_type = resolve_provider(model)

    base_url = proxy.ag_base_url if provider_type == "gemini-antigravity" else f"{proxy.base_url}/{provider_type}"
    url = f"{base_url}/v1/messages"

    headers = proxy._build_headers(provider_type)
    headers["x-api-key"] = headers.get("Authorization", "").replace("Bearer ", "")
    headers["anthropic-version"] = body.pop("anthropic_version", None) or raw_request.headers.get("anthropic-version", "2023-06-01")
    headers["Content-Type"] = "application/json"

    is_stream = body.get("stream", False)

    if is_stream:
        req = proxy.client.build_request("POST", url, json=body, headers=headers)
        upstream = await proxy.client.send(req, stream=True)

        if upstream.status_code != 200:
            error_body = await upstream.aread()
            await upstream.aclose()
            raise HTTPException(
                status_code=upstream.status_code,
                detail=error_body.decode("utf-8", errors="replace")[:500],
            )

        return StreamingResponse(
            _transparent_stream(
                upstream, start_time, user, background_tasks, request_id,
                model, provider_type, input_tokens, client_ip, "anthropic",
            ),
            status_code=200,
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    # ── Non-streaming ────────────────────────
    response = await proxy.client.post(url, json=body, headers=headers, timeout=httpx.Timeout(120.0))
    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail=response.text[:500])

    data = response.json()
    output_tokens = data.get("usage", {}).get("output_tokens", 0)
    if output_tokens == 0:
        for block in data.get("content", []):
            if block.get("type") == "text":
                output_tokens += count_tokens(block.get("text", ""))

    elapsed_ms = int((time.monotonic() - start_time) * 1000)
    pricing = await get_model_pricing(db, model, provider_type)
    cost = calculate_cost(input_tokens, output_tokens, pricing)

    if user["user_id"] != "master":
        await db.execute(
            text("UPDATE users SET credit_balance = credit_balance - :cost WHERE id = :user_id AND credit_balance >= :cost"),
            {"cost": cost, "user_id": user["user_id"]},
        )
        await db.commit()

    await record_usage(
        db=db, user_id=user["user_id"], api_key_id=user["api_key_id"],
        request_id=request_id, model_requested=model, model_used=model,
        provider_type=provider_type, input_tokens=input_tokens,
        output_tokens=output_tokens,
        credits_charged=cost if user["user_id"] != "master" else 0,
        latency_ms=elapsed_ms, status="success", error_message=None,
        ip_address=client_ip,
    )
    return data


@router.post("/v1beta/models/{model_name}:generateContent")
@router.post("/v1beta/models/{model_name}:streamGenerateContent")
async def gemini_generate_content(
    model_name: str,
    raw_request: Request,
    background_tasks: BackgroundTasks,
    user: dict = Depends(verify_api_key),
    db=Depends(get_db),
):
    """Native Gemini generateContent passthrough."""
    body = await raw_request.json()
    client_ip = raw_request.client.host if raw_request.client else None
    request_id = f"gmn_{uuid.uuid4().hex[:24]}"
    start_time = time.monotonic()

    input_tokens = count_gemini_tokens(body)
    provider_type = resolve_provider(model_name)
    base_url = proxy.ag_base_url if provider_type == "gemini-antigravity" else f"{proxy.base_url}/{provider_type}"

    is_stream = "stream" in raw_request.url.path
    action = "streamGenerateContent" if is_stream else "generateContent"

    api_key = proxy._build_headers(provider_type).get("Authorization", "").replace("Bearer ", "")
    url = f"{base_url}/v1beta/models/{model_name}:{action}?key={api_key}"
    if is_stream:
        url += "&alt=sse"

    headers = {"Content-Type": "application/json"}

    if is_stream:
        req = proxy.client.build_request("POST", url, json=body, headers=headers)
        upstream = await proxy.client.send(req, stream=True)

        if upstream.status_code != 200:
            error_body = await upstream.aread()
            await upstream.aclose()
            raise HTTPException(status_code=upstream.status_code, detail=error_body.decode()[:500])

        return StreamingResponse(
            _transparent_stream(
                upstream, start_time, user, background_tasks, request_id, 
                model_name, provider_type, input_tokens, client_ip, "gemini",
            ),
            status_code=200,
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    response = await proxy.client.post(url, json=body, headers=headers, timeout=httpx.Timeout(120.0))
    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail=response.text[:500])

    data = response.json()
    output_tokens = 0
    candidates = data.get("candidates", [])
    if candidates:
        parts = candidates[0].get("content", {}).get("parts", [])
        output_tokens = count_tokens("".join(p.get("text", "") for p in parts if "text" in p))

    elapsed_ms = int((time.monotonic() - start_time) * 1000)
    pricing = await get_model_pricing(db, model_name, provider_type)
    cost = calculate_cost(input_tokens, output_tokens, pricing)

    if user["user_id"] != "master":
        await db.execute(
            text("UPDATE users SET credit_balance = credit_balance - :cost WHERE id = :user_id AND credit_balance >= :cost"),
            {"cost": cost, "user_id": user["user_id"]},
        )
        await db.commit()

    await record_usage(
        db=db, user_id=user["user_id"], api_key_id=user["api_key_id"],
        request_id=request_id, model_requested=model_name, model_used=model_name,
        provider_type=provider_type, input_tokens=input_tokens,
        output_tokens=output_tokens,
        credits_charged=cost if user["user_id"] != "master" else 0,
        latency_ms=elapsed_ms, status="success", error_message=None,
        ip_address=client_ip,
    )
    return data
