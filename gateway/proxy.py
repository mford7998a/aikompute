"""
Proxy module: forwards requests to AIClient-2-API and transforms responses.

AIClient-2-API already handles:
  - Protocol transformation (Gemini CLI → OpenAI, Kiro → OpenAI, etc.)
  - Account pool rotation with health checks
  - Fallback chains between provider types
  - OAuth credential management and token refresh

This module:
  - Forwards OpenAI-compatible requests to AIClient-2-API
  - Extracts token usage from responses for billing
  - Handles streaming (SSE passthrough with token counting)
  - Maps user-requested model names to AIClient-2-API provider routes
  - Circuit breaker + health scoring per provider (via circuit_breaker module)
  - Session stickiness: same session_id → same provider for SESSION_TTL_S seconds
"""
import json
import logging
import time
import uuid
from typing import AsyncGenerator, Optional

import httpx
from fastapi import HTTPException
from config import settings
from circuit_breaker import (
    best_available_providers,
    record_provider_success,
    record_provider_failure,
    get_session_provider,
    pin_session_provider,
    clear_session_provider,
)

log = logging.getLogger(__name__)


# ============================================
# Model → Provider Route Mapping
# ============================================
# AIClient-2-API uses path-based routing:
#   /gemini-cli-oauth/v1/chat/completions   → Gemini CLI
#   /gemini-antigravity/v1/chat/completions  → Antigravity
#   /claude-kiro-oauth/v1/chat/completions   → Kiro (Claude)
#   /openai-qwen-oauth/v1/chat/completions   → Qwen Code
#   /openai-custom/v1/chat/completions       → OpenAI direct
#   /claude-custom/v1/chat/completions       → Claude direct

MODEL_TO_PROVIDER = {
    # Gemini models → route through Antigravity (user has these accounts)
    "gemini-2.0-flash": "gemini-antigravity",
    "gemini-2.5-pro": "gemini-antigravity",
    "gemini-2.5-flash": "gemini-antigravity",
    "gemini-3.0-pro": "gemini-antigravity",
    "gemini-3.0-flash": "gemini-antigravity",
    "gemini-3.1-pro-high": "gemini-antigravity",
    "gemini-3.1-pro-low": "gemini-antigravity",
    "gemini-3.5-flash": "gemini-antigravity",
    "gemini-pro": "gemini-antigravity",
    "gemini-flash": "gemini-antigravity",
    # Also accept the raw model names Antigravity uses
    "gemini-2.5-computer-use-preview-10-2025": "gemini-antigravity",

    # Verdent proxy requests
    "verdent": "verdent2api",
    "verdent-chat": "verdent2api",
    "verdent-agent": "verdent2api",

    # Claude models → Kiro first (AG is the fallback in config.json/proxy logic)
    "claude-sonnet-4-6": "gemini-antigravity",
    "claude-opus-4-6": "gemini-antigravity",
    "claude-sonnet-4-5": "claude-kiro-oauth",
    "claude-sonnet-4": "claude-kiro-oauth",
    "claude-opus-4-5": "claude-kiro-oauth",
    "claude-opus-4": "claude-kiro-oauth",
    "claude-haiku-3-5": "claude-kiro-oauth",
    "kiro-claude-opus-4-5-thinking": "claude-kiro-oauth",
    "kiro-claude-sonnet-4-5": "claude-kiro-oauth",

    # Qwen models → route through Qwen OAuth
    "qwen3-coder-plus": "openai-qwen-oauth",
    "qwen3-coder": "openai-qwen-oauth",
    "qwen-turbo": "openai-qwen-oauth",

    # GitHub Models — free GPT-4o / Claude / Gemini via GitHub PAT
    "github-gpt-4o": "github-models",
    "github-claude-sonnet": "github-models",
    "github-gemini-pro": "github-models",
    "github-gpt-4.1": "github-models",
    "github-o4-mini": "github-models",
    "github-deepseek-v3": "github-models",

    # Copilot-API — GitHub Copilot Free/Pro/Enterprise → OpenAI/Anthropic proxy
    # No API key required — uses GitHub OAuth (authenticated once on container start).
    # Gives access to GPT-4o, Claude Sonnet, o4-mini via Copilot subscription.
    "copilot-gpt-4o":           "copilot-api",
    "copilot-gpt-4.1":          "copilot-api",
    "copilot-o4-mini":          "copilot-api",
    "copilot-claude-sonnet":    "copilot-api",
    "copilot-claude-haiku":     "copilot-api",

    # Direct API models (paid keys)
    "claude-3-5-sonnet": "claude-custom",
    "gpt-4o": "openai-iflow",
    "deepseek-v3": "openai-iflow",
    "deepseek-r1": "openai-iflow",
    "trae-gpt-4o": "webai2api",
    "marscode-gpt-4o": "webai2api",
}

# GitHub model name → actual model ID used by GitHub Models API
GITHUB_MODEL_MAP = {
    "github-gpt-4o":          "gpt-4o",
    "github-gpt-4.1":         "gpt-4.1",
    "github-o4-mini":         "o4-mini",
    "github-claude-sonnet":   "claude-sonnet-4-5",
    "github-gemini-pro":      "gemini-2.0-flash",
    "github-deepseek-v3":     "deepseek-v3-0324",
}

# Copilot model name → actual model ID passed to copilot-api
# copilot-api passes these straight to Copilot's backend.
COPILOT_MODEL_MAP = {
    "copilot-gpt-4o":        "gpt-4o",
    "copilot-gpt-4.1":       "gpt-4.1",
    "copilot-o4-mini":       "o4-mini",
    "copilot-claude-sonnet": "claude-sonnet-4-5",
    "copilot-claude-haiku":  "claude-haiku-3-5",
}

# Provider type labels for usage logs
PROVIDER_LABELS = {
    "gemini-cli-oauth": "Standard API",
    "gemini-antigravity": "Standard API",
    "claude-kiro-oauth": "Standard API",
    "openai-qwen-oauth": "Standard API",
    "openai-custom": "Standard API",
    "claude-custom": "Standard API",
    "openai-iflow": "Standard API",
    "webai2api": "Standard API",
    "github-models": "GitHub Models",
    "copilot-api": "GitHub Copilot",
    "verdent2api": "Verdent Native",
}

# Auto-routing: antigravity first since that's what we have
AUTO_ROUTE_ORDER = [
    "verdent2api",
    "gemini-antigravity",
    "gemini-cli-oauth",
    "claude-kiro-oauth",
    "openai-qwen-oauth",
    "copilot-api",       # free Copilot quota — ranked before paid providers
    "github-models",
    "openai-custom",
    "openai-iflow",
    "webai2api",
    "claude-custom",
]


def resolve_provider(model: str) -> str:
    """
    Determine which provider route to use for a model.

    If the model is in our explicit mapping, use that.
    Otherwise, try to infer from the model name prefix.
    """
    # Exact match
    if model in MODEL_TO_PROVIDER:
        return MODEL_TO_PROVIDER[model]

    # Prefix-based inference
    model_lower = model.lower()
    if model_lower.startswith("github-"):
        return "github-models"
    elif model_lower.startswith("copilot-"):
        return "copilot-api"
    elif model_lower.startswith("gemini"):
        return "gemini-antigravity"   # we have Antigravity accounts
    elif model_lower.startswith("claude"):
        return "claude-kiro-oauth"
    elif model_lower.startswith("qwen"):
        return "openai-qwen-oauth"
    elif model_lower.startswith("verdent"):
        return "verdent2api"
    elif model_lower.startswith("gpt"):
        return "openai-custom"

    # Default: antigravity (our primary free provider)
    return "gemini-antigravity"


def get_provider_for_auto(preferred_providers: Optional[list] = None) -> str:
    """Get the first provider for 'auto' model routing."""
    order = preferred_providers or AUTO_ROUTE_ORDER
    return order[0] if order else "gemini-cli-oauth"


class AIClient2APIProxy:
    """
    Proxies requests to AIClient-2-API, which handles:
    - Simulating Gemini CLI, Antigravity, Kiro, Qwen client requests
    - Converting them to OpenAI-compatible responses
    - Account pool rotation and health checks
    - Automatic fallback between provider types
    """

    def __init__(self):
        self.base_url = settings.AICLIENT2API_BASE_URL.rstrip("/")
        self.api_key = settings.AICLIENT2API_KEY
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(120.0, connect=10.0),
            limits=httpx.Limits(max_connections=100, max_keepalive_connections=20),
        )
        # Antigravity specific backend
        self.ag_base_url = settings.ANTIGRAVITY2API_BASE_URL.rstrip("/")
        self.ag_api_key = settings.ANTIGRAVITY2API_KEY
        # WebAI2API specific backend (Trae/MarsCode)
        self.webai_base_url = settings.WEBAI2API_BASE_URL.rstrip("/")
        self.webai_api_key = settings.WEBAI2API_KEY
        # Verdent2api backend (Local Verdent agent)
        self.verdent_base_url = settings.VERDENT2API_BASE_URL.rstrip("/")
        self.verdent_api_key = settings.VERDENT2API_KEY
        # GitHub Models backend (free inference API via GitHub PAT)
        self.github_models_url = "https://models.inference.ai.azure.com"
        self.github_token = settings.GITHUB_TOKEN
        # Copilot-API backend (GitHub Copilot → OpenAI/Anthropic proxy)
        self.copilot_base_url = settings.COPILOT_API_BASE_URL.rstrip("/")

    async def close(self):
        await self.client.aclose()

    def _build_url(self, provider_type: str, path: str = "/v1/chat/completions") -> str:
        """
        Build the upstream URL for a given provider.

        - gemini-antigravity → specialized Antigravity-2-API service
        - webai2api          → WebAI2API service (Trae/MarsCode)
        - github-models      → GitHub Models inference API (Azure-hosted)
        - copilot-api        → ericc-ch/copilot-api (GitHub Copilot proxy)
        - all others         → AIClient-2-API path-prefix routing
        """
        if provider_type == "gemini-antigravity":
            return f"{self.ag_base_url}{path}"
        elif provider_type == "webai2api":
            return f"{self.webai_base_url}{path}"
        elif provider_type == "verdent2api":
            return f"{self.verdent_base_url}{path}"
        elif provider_type == "github-models":
            # GitHub Models uses the standard /v1/chat/completions path
            return f"{self.github_models_url}/v1/chat/completions"
        elif provider_type == "copilot-api":
            # copilot-api exposes a standard OpenAI-compatible endpoint
            return f"{self.copilot_base_url}/v1/chat/completions"

        # AIClient-2-API routes by path prefix
        return f"{self.base_url}/{provider_type}{path}"

    def _build_headers(self, provider_type: str = "generic") -> dict:
        if provider_type == "gemini-antigravity":
            key = self.ag_api_key
        elif provider_type == "webai2api":
            key = self.webai_api_key
        elif provider_type == "verdent2api":
            key = self.verdent_api_key
        elif provider_type == "github-models":
            key = self.github_token
        elif provider_type == "copilot-api":
            # copilot-api doesn't require an API key — auth is handled internally
            # via the GitHub OAuth token stored in the container's data volume.
            # We send a dummy bearer so the header is well-formed.
            key = "copilot"
        else:
            key = self.api_key

        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {key}",
        }

    def _translate_model_for_provider(self, model: str, provider_type: str) -> str:
        """Translate gateway model alias to the real model ID expected by the upstream."""
        if provider_type == "github-models":
            return GITHUB_MODEL_MAP.get(model, model)
        if provider_type == "copilot-api":
            return COPILOT_MODEL_MAP.get(model, model)
        return model

    async def chat_completion(
        self,
        model: str,
        messages: list,
        provider_type: str,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        stream: bool = False,
        **kwargs,
    ) -> dict:
        """
        Send a non-streaming chat completion request.
        
        Returns the full OpenAI-compatible response dict with usage info.
        """
        url = self._build_url(provider_type)
        
        upstream_model = self._translate_model_for_provider(model, provider_type)
        payload = {
            "model": upstream_model,
            "messages": messages,
            "temperature": temperature,
            "stream": False,
        }
        if max_tokens:
            payload["max_tokens"] = max_tokens

        # Pass through any extra params (top_p, etc.)
        for key in ("top_p", "frequency_penalty", "presence_penalty", "stop"):
            if key in kwargs and kwargs[key] is not None:
                payload[key] = kwargs[key]

        start_time = time.monotonic()

        try:
            response = await self.client.post(
                url,
                json=payload,
                headers=self._build_headers(provider_type),
            )
        except httpx.TimeoutException:
            await record_provider_failure(provider_type)
            raise HTTPException(status_code=504, detail="Upstream provider timed out")
        except httpx.ConnectError:
            await record_provider_failure(provider_type)
            raise HTTPException(status_code=502, detail="Cannot connect to inference backend")

        elapsed_ms = int((time.monotonic() - start_time) * 1000)

        if response.status_code == 429:
            await record_provider_failure(provider_type)
            raise HTTPException(
                status_code=429,
                detail="Provider rate limit reached. Please retry in a moment.",
            )

        if response.status_code != 200:
            await record_provider_failure(provider_type)
            error_text = response.text[:500]
            raise HTTPException(
                status_code=response.status_code,
                detail=f"Upstream error: {error_text}",
            )

        await record_provider_success(provider_type)
        data = response.json()

        # ── Defensive: aiclient2api sometimes returns HTTP 200 but wraps
        # an upstream error (e.g. 429 rate-limit) in the body instead of
        # raising a proper error status. Detect this and surface it correctly.
        if "error" in data and "choices" not in data:
            err = data["error"]
            err_code = err.get("code", "") if isinstance(err, dict) else str(err)
            err_msg  = err.get("message", str(err)) if isinstance(err, dict) else str(err)
            await record_provider_failure(provider_type)

            if "429" in err_msg or "rate_limit" in err_code:
                raise HTTPException(
                    status_code=429,
                    detail=f"Provider rate limit reached ({provider_type}). Please retry in a moment.",
                )
            raise HTTPException(
                status_code=502,
                detail=f"Upstream error from {provider_type}: {err_msg[:200]}",
            )

        data["_latency_ms"] = elapsed_ms
        data["_provider_type"] = provider_type
        return data

    async def chat_completion_stream(
        self,
        model: str,
        messages: list,
        provider_type: str,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs,
    ) -> AsyncGenerator[str, None]:
        """
        Stream a chat completion. Yields SSE-formatted chunks.
        
        Also accumulates text for post-stream token counting.
        """
        url = self._build_url(provider_type)

        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "stream": True,
        }
        if max_tokens:
            payload["max_tokens"] = max_tokens

        for key in ("top_p", "frequency_penalty", "presence_penalty", "stop"):
            if key in kwargs and kwargs[key] is not None:
                payload[key] = kwargs[key]

        request_id = f"chatcmpl-{uuid.uuid4().hex[:24]}"
        accumulated_text = ""

        try:
            async with self.client.stream(
                "POST",
                url,
                json=payload,
                headers=self._build_headers(provider_type),
                timeout=httpx.Timeout(120.0, connect=10.0),
            ) as response:
                if response.status_code != 200:
                    error_body = await response.aread()
                    raise HTTPException(
                        status_code=response.status_code,
                        detail=f"Upstream error: {error_body.decode()[:500]}",
                    )

                async for line in response.aiter_lines():
                    if not line:
                        continue
                    if line.startswith("data: "):
                        data_str = line[6:]
                        if data_str.strip() == "[DONE]":
                            yield "data: [DONE]\n\n"
                            break

                        try:
                            chunk = json.loads(data_str)
                            # Override the ID to be consistent
                            chunk["id"] = request_id

                            # Accumulate text for token counting
                            choices = chunk.get("choices", [])
                            if choices:
                                delta = choices[0].get("delta", {})
                                content = delta.get("content", "")
                                if content:
                                    accumulated_text += content

                            yield f"data: {json.dumps(chunk)}\n\n"
                        except json.JSONDecodeError:
                            yield f"data: {data_str}\n\n"

        except httpx.TimeoutException:
            yield f'data: {{"error": "Stream timed out"}}\n\n'
        except httpx.ConnectError:
            yield f'data: {{"error": "Cannot connect to backend"}}\n\n'

        # Store accumulated text for billing (accessed via _stream_text attribute)
        self._last_stream_text = accumulated_text
        self._last_stream_request_id = request_id

    async def generic_proxy(
        self,
        path: str,
        payload: dict,
        provider_type: str,
        method: str = "POST",
    ) -> dict:
        """
        Generic proxy for any endpoint (v1/messages, v1beta/models, etc.)
        """
        url = self._build_url(provider_type, path)
        start_time = time.monotonic()

        try:
            response = await self.client.request(
                method,
                url,
                json=payload,
                headers=self._build_headers(provider_type),
            )
        except httpx.TimeoutException:
            raise HTTPException(status_code=504, detail="Upstream provider timed out")
        except httpx.ConnectError:
            raise HTTPException(status_code=502, detail="Cannot connect to inference backend")

        elapsed_ms = int((time.monotonic() - start_time) * 1000)

        if response.status_code != 200:
            error_text = response.text[:500]
            raise HTTPException(
                status_code=response.status_code,
                detail=f"Upstream error: {error_text}",
            )

        data = response.json()
        data["_latency_ms"] = elapsed_ms
        data["_provider_type"] = provider_type
        return data

    async def generic_proxy_stream(
        self,
        path: str,
        payload: dict,
        provider_type: str,
    ) -> AsyncGenerator[str, None]:
        """
        Generic streaming proxy for any endpoint.
        """
        url = self._build_url(provider_type, path)
        request_id = f"gen-{uuid.uuid4().hex[:24]}"
        accumulated_text = ""

        try:
            async with self.client.stream(
                "POST",
                url,
                json=payload,
                headers=self._build_headers(provider_type),
                timeout=httpx.Timeout(120.0, connect=10.0),
            ) as response:
                if response.status_code != 200:
                    error_body = await response.aread()
                    raise HTTPException(
                        status_code=response.status_code,
                        detail=f"Upstream error: {error_body.decode()[:500]}",
                    )

                async for line in response.aiter_lines():
                    if not line:
                        continue
                    if line.startswith("data: "):
                        data_str = line[6:]
                        if data_str.strip() == "[DONE]":
                            yield "data: [DONE]\n\n"
                            break

                        try:
                            # Try to extract content for billing
                            # Different formats (Gemini vs Claude) have different chunk structures
                            # We'll try to be generic or just yield it
                            data = json.loads(data_str)
                            
                            # Anthropic chunk
                            if "type" in data and data["type"] == "content_block_delta":
                                delta = data.get("delta", {})
                                if delta.get("type") == "text_delta":
                                    accumulated_text += delta.get("text", "")
                            
                            # Gemini chunk (candidates[0].content.parts[0].text)
                            elif "candidates" in data:
                                try:
                                    text = data["candidates"][0]["content"]["parts"][0]["text"]
                                    accumulated_text += text
                                except (KeyError, IndexError):
                                    pass

                            yield f"data: {data_str}\n\n"
                        except json.JSONDecodeError:
                            yield f"data: {data_str}\n\n"

        except Exception as e:
            yield f'data: {{"error": "{str(e)}"}}\n\n'

        self._last_stream_text = accumulated_text
        self._last_stream_request_id = request_id

    async def try_with_fallback(
        self,
        model: str,
        messages: list,
        providers_to_try: list,
        session_id: str = "",
        **kwargs,
    ) -> dict:
        """
        Try multiple providers in order until one succeeds.

        Before iterating, the list is:
          1. Re-ordered by circuit breaker state + health score (best first).
          2. Filtered so OPEN circuits are skipped entirely.

        Session stickiness: if session_id is set and a pin exists in Redis,
        attempt the pinned provider before falling back to the ranked list.
        """
        last_error = None

        # -- Session stickiness: try pinned provider first --
        if session_id:
            pinned = await get_session_provider(session_id)
            if pinned and pinned in providers_to_try:
                try:
                    result = await self.chat_completion(
                        model=model,
                        messages=messages,
                        provider_type=pinned,
                        **kwargs,
                    )
                    # Refresh the TTL on success
                    await pin_session_provider(session_id, pinned)
                    return result
                except HTTPException:
                    # Pinned provider failed; fall through to ranked list
                    await clear_session_provider(session_id)

        # -- Re-rank remaining providers by circuit state + health score --
        ranked = await best_available_providers(providers_to_try)

        for provider_type in ranked:
            try:
                result = await self.chat_completion(
                    model=model,
                    messages=messages,
                    provider_type=provider_type,
                    **kwargs,
                )
                # Pin this session to the winning provider
                if session_id:
                    await pin_session_provider(session_id, provider_type)
                return result
            except HTTPException as e:
                last_error = e
                # NOTE: Upstream providers (like aiclient2api or Kiro) often wrap 
                # auth/capacity failures in a 400 Bad Request instead of a 429.
                # Therefore, we treat 400 as a retriable error to trigger the fallback chain.
                if e.status_code in (400, 429, 503, 502, 504):
                    continue  # Retriable: try next provider
                else:
                    raise  # Client error (4xx), don't retry

        raise last_error or HTTPException(502, "All providers failed")


# Singleton
proxy = AIClient2APIProxy()
