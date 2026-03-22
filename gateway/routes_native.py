from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
import time
import uuid
import json

from auth import verify_api_key
from billing import (
    count_anthropic_tokens,
    count_gemini_tokens,
    get_model_pricing,
    calculate_cost,
    record_usage,
    count_tokens
)
from database import get_db
from proxy import proxy, resolve_provider, resolve_fallback_providers

router = APIRouter()

async def _stream_native(response_stream, start_time, user, db, request_id, model, provider_type, input_tokens, client_ip, vendor):
    """Accumulates text from native SSE and bills based on the generated text blocks."""
    accumulated_text = ""
    try:
        async for chunk in response_stream:
            yield chunk
            
            # Simple chunk parsing to accumulate text for billing
            if not chunk.strip() or not chunk.startswith("data: "):
                continue
                
            try:
                data_str = chunk[6:].strip()
                if data_str == "[DONE]":
                    continue
                data = json.loads(data_str)
                
                # Anthropic: {"type": "content_block_delta", "delta": {"text": "..."}}
                if vendor == "anthropic" and data.get("type") == "content_block_delta":
                    accumulated_text += data.get("delta", {}).get("text", "")
                    
                # Gemini: (Gemini SSE wrapper or chunked json)
                elif vendor == "gemini":
                    # Gemini usually returns a list or direct object with candidates
                    candidates = data.get("candidates", [])
                    if candidates:
                        parts = candidates[0].get("content", {}).get("parts", [])
                        for p in parts:
                            accumulated_text += p.get("text", "")
            except Exception:
                pass
    finally:
        # Billing logic
        output_tokens = count_tokens(accumulated_text)
        total_tokens = input_tokens + output_tokens
        elapsed_ms = int((time.monotonic() - start_time) * 1000)
        
        # We did not pre-charge for streams here to keep it simple, but we can charge actual usage
        pricing = await get_model_pricing(db, model, provider_type)
        cost = calculate_cost(input_tokens, output_tokens, pricing)
        
        if user["user_id"] != "master":
            await db.execute(
                "UPDATE users SET credit_balance = credit_balance - :cost WHERE id = :user_id AND credit_balance >= :cost",
                {"cost": cost, "user_id": user["user_id"]}
            )
            await db.commit()
            
        await record_usage(
            db=db, user_id=user["user_id"], api_key_id=user["api_key_id"],
            request_id=request_id, model_requested=model, model_used=model,
            provider_type=provider_type, input_tokens=input_tokens,
            output_tokens=output_tokens, credits_charged=cost if user["user_id"] != "master" else 0,
            latency_ms=elapsed_ms, status="success", error_message=None, ip_address=client_ip
        )


@router.post("/v1/messages")
async def anthropic_messages(
    raw_request: Request,
    user: dict = Depends(verify_api_key),
    db = Depends(get_db)
):
    """Native Anthropic Endpoint"""
    body = await raw_request.json()
    model = body.get("model", "")
    if not model:
        raise HTTPException(status_code=400, detail="model is required")
        
    client_ip = raw_request.client.host if raw_request.client else None
    request_id = f"msg_{uuid.uuid4().hex[:24]}"
    start_time = time.monotonic()
    
    input_tokens = count_anthropic_tokens(body)
    provider_type = resolve_provider(model)
    
    # We cheat and just proxy to the provider's /v1/messages instead of /v1/chat/completions!
    # Currently proxy.py expects to add `/v1/chat/completions`. We bypass proxy.py's URL builder
    # and call it manually.
    
    base_url = proxy.ag_base_url if provider_type == "gemini-antigravity" else f"{proxy.base_url}/{provider_type}"
    url = f"{base_url}/v1/messages"
    
    headers = proxy._build_headers(provider_type)
    headers["x-api-key"] = headers.get("Authorization", "").replace("Bearer ", "") # Many Anthropic proxies need x-api-key
    headers["anthropic-version"] = "2023-06-01"
    
    if body.get("stream"):
        async def stream_generator():
            async with proxy.client.stream("POST", url, json=body, headers=headers) as response:
                if response.status_code != 200:
                    yield f"data: {json.dumps({'error': {'message': 'Upstream error', 'type': 'api_error'}})}\n\n"
                    return
                async for line in response.aiter_lines():
                    if line:
                        yield line + "\n"
        
        return StreamingResponse(
            _stream_native(stream_generator(), start_time, user, db, request_id, model, provider_type, input_tokens, client_ip, "anthropic"),
            media_type="text/event-stream"
        )
    else:
        response = await proxy.client.post(url, json=body, headers=headers)
        if response.status_code != 200:
            raise HTTPException(status_code=response.status_code, detail=response.text[:500])
            
        data = response.json()
        output_tokens = data.get("usage", {}).get("output_tokens", 0)
        
        elapsed_ms = int((time.monotonic() - start_time) * 1000)
        pricing = await get_model_pricing(db, model, provider_type)
        cost = calculate_cost(input_tokens, output_tokens, pricing)
        
        if user["user_id"] != "master":
            await db.execute(
                "UPDATE users SET credit_balance = credit_balance - :cost WHERE id = :user_id AND credit_balance >= :cost",
                {"cost": cost, "user_id": user["user_id"]}
            )
            await db.commit()
            
        await record_usage(
            db=db, user_id=user["user_id"], api_key_id=user["api_key_id"],
            request_id=request_id, model_requested=model, model_used=model,
            provider_type=provider_type, input_tokens=input_tokens,
            output_tokens=output_tokens, credits_charged=cost if user["user_id"] != "master" else 0,
            latency_ms=elapsed_ms, status="success", error_message=None, ip_address=client_ip
        )
        return data


@router.post("/v1beta/models/{model}:generateContent")
@router.post("/v1beta/models/{model}:streamGenerateContent")
async def gemini_generate_content(
    model: str,
    raw_request: Request,
    user: dict = Depends(verify_api_key),
    db = Depends(get_db)
):
    """Native Gemini Endpoint"""
    body = await raw_request.json()
    client_ip = raw_request.client.host if raw_request.client else None
    request_id = f"gmn_{uuid.uuid4().hex[:24]}"
    start_time = time.monotonic()
    
    input_tokens = count_gemini_tokens(body)
    provider_type = resolve_provider(model)
    base_url = proxy.ag_base_url if provider_type == "gemini-antigravity" else f"{proxy.base_url}/{provider_type}"
    url_path = "streamGenerateContent" if "stream" in raw_request.url.path else "generateContent"
    
    url = f"{base_url}/v1beta/models/{model}:{url_path}?key={proxy._build_headers(provider_type).get('Authorization', '').replace('Bearer ', '')}"
    headers = {"Content-Type": "application/json"}
    
    if "stream" in url_path or raw_request.query_params.get("alt") == "sse":
        url += "&alt=sse"
        async def stream_generator():
            async with proxy.client.stream("POST", url, json=body, headers=headers) as response:
                if response.status_code != 200:
                    yield f"data: {json.dumps({'error': {'message': 'Upstream error', 'type': 'api_error'}})}\n\n"
                    return
                async for line in response.aiter_lines():
                    if line:
                        yield line + "\n"
                        
        return StreamingResponse(
            _stream_native(stream_generator(), start_time, user, db, request_id, model, provider_type, input_tokens, client_ip, "gemini"),
            media_type="text/event-stream"
        )
    else:
        response = await proxy.client.post(url, json=body, headers=headers)
        if response.status_code != 200:
            raise HTTPException(status_code=response.status_code, detail=response.text[:500])
            
        data = response.json()
        
        # Count tokens from un-streamed json
        output_tokens = 0
        candidates = data.get("candidates", [])
        if candidates:
            parts = candidates[0].get("content", {}).get("parts", [])
            accumulated_text = "".join([p.get("text", "") for p in parts if "text" in p])
            output_tokens = count_tokens(accumulated_text)
            
        elapsed_ms = int((time.monotonic() - start_time) * 1000)
        pricing = await get_model_pricing(db, model, provider_type)
        cost = calculate_cost(input_tokens, output_tokens, pricing)
        
        if user["user_id"] != "master":
            await db.execute(
                "UPDATE users SET credit_balance = credit_balance - :cost WHERE id = :user_id AND credit_balance >= :cost",
                {"cost": cost, "user_id": user["user_id"]}
            )
            await db.commit()
            
        await record_usage(
            db=db, user_id=user["user_id"], api_key_id=user["api_key_id"],
            request_id=request_id, model_requested=model, model_used=model,
            provider_type=provider_type, input_tokens=input_tokens,
            output_tokens=output_tokens, credits_charged=cost if user["user_id"] != "master" else 0,
            latency_ms=elapsed_ms, status="success", error_message=None, ip_address=client_ip
        )
        return data
