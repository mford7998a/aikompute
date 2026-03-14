#!/usr/bin/env python3
"""
End-to-End Gateway Test
=======================
Simulates a real customer:
  1. Registers a fresh account
  2. Uses the issued API key to call each model
  3. Reports pass/fail + latency for every model

Usage:
    python scripts/test_gateway.py
    python scripts/test_gateway.py --base-url http://my-server:4000
    python scripts/test_gateway.py --key sk-existing-key  # use an existing key
"""
import argparse
import asyncio
import time
import sys
import json
import uuid
from datetime import datetime

import httpx

# ──────────────────────────────────────────────
BASE_URL = "http://localhost:4000"
TEST_PROMPT = "Reply with exactly: OK"

# All models from proxy.py MODEL_TO_PROVIDER
ALL_MODELS = [
    # Gemini via Antigravity
    ("gemini-2.0-flash",        "Gemini 2.0 Flash (Antigravity)"),
    ("gemini-2.5-pro",          "Gemini 2.5 Pro (Antigravity)"),
    ("gemini-2.5-flash",        "Gemini 2.5 Flash (Antigravity)"),
    # Claude via Kiro
    ("claude-sonnet-4-5",       "Claude Sonnet 4.5 (Kiro)"),
    ("claude-opus-4-5",         "Claude Opus 4.5 (Kiro)"),
    # Qwen
    ("qwen-turbo",              "Qwen Turbo (Qwen OAuth)"),
    ("qwen3-coder",             "Qwen3 Coder (Qwen OAuth)"),
    ("qwen3-coder-plus",        "Qwen3 Coder Plus (Qwen OAuth)"),
    # GitHub Models
    ("github-gpt-4o",           "GPT-4o (GitHub Models)"),
    ("github-gpt-4.1",          "GPT-4.1 (GitHub Models)"),
    ("github-gemini-pro",       "Gemini Pro (GitHub Models)"),
    ("github-claude-sonnet",    "Claude Sonnet (GitHub Models)"),
    ("github-deepseek-v3",      "DeepSeek V3 (GitHub Models)"),
    ("github-o4-mini",          "o4-mini (GitHub Models)"),
    # Copilot
    ("copilot-gpt-4o",          "GPT-4o (Copilot)"),
    ("copilot-gpt-4.1",         "GPT-4.1 (Copilot)"),
    ("copilot-claude-sonnet",   "Claude Sonnet (Copilot)"),
    ("copilot-o4-mini",         "o4-mini (Copilot)"),
    # Trae/Webai
    ("trae-gpt-4o",             "GPT-4o (Trae)"),
]

GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
RESET  = "\033[0m"
BOLD   = "\033[1m"


def log(msg, color=""):
    print(f"{color}{msg}{RESET}")


async def register_test_user(client: httpx.AsyncClient) -> str:
    """Create a fresh test account and return the API key."""
    uid = uuid.uuid4().hex[:8]
    email = f"test-{uid}@gateway-test.local"
    password = "TestP@ssw0rd!"

    log(f"\n{'='*60}", CYAN)
    log(f"  STEP 1 — Registering test user: {email}", CYAN)
    log(f"{'='*60}", CYAN)

    resp = await client.post(f"{BASE_URL}/api/auth/register", json={
        "email": email,
        "password": password,
        "display_name": f"Test User {uid}",
    })

    if resp.status_code != 200:
        log(f"❌ Registration failed: {resp.status_code} {resp.text}", RED)
        sys.exit(1)

    data = resp.json()
    api_key = data["api_key"]
    balance = data.get("credit_balance", 0)

    log(f"  ✅ Registered! User ID : {data['user_id']}", GREEN)
    log(f"  🔑 API Key      : {api_key}", GREEN)
    log(f"  💳 Free Credits  : {balance:,}", GREEN)

    return api_key


async def test_model(
    client: httpx.AsyncClient,
    api_key: str,
    model: str,
    label: str,
) -> dict:
    """Send a single chat completion and return result metadata."""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": TEST_PROMPT}],
        "max_tokens": 20,
        "stream": False,
    }

    start = time.perf_counter()
    try:
        resp = await client.post(
            f"{BASE_URL}/v1/chat/completions",
            json=payload,
            headers=headers,
            timeout=45,
        )
        latency = int((time.perf_counter() - start) * 1000)

        if resp.status_code == 200:
            data = resp.json()
            content = data["choices"][0]["message"]["content"].strip()
            usage = data.get("usage", {})
            return {
                "model": model,
                "label": label,
                "ok": True,
                "latency_ms": latency,
                "response": content[:60],
                "input_tokens": usage.get("prompt_tokens", "?"),
                "output_tokens": usage.get("completion_tokens", "?"),
            }
        else:
            return {
                "model": model,
                "label": label,
                "ok": False,
                "latency_ms": latency,
                "error": f"HTTP {resp.status_code}",
                "detail": resp.text[:120],
            }

    except httpx.TimeoutException:
        latency = int((time.perf_counter() - start) * 1000)
        return {
            "model": model,
            "label": label,
            "ok": False,
            "latency_ms": latency,
            "error": "TIMEOUT (>45s)",
        }
    except Exception as e:
        latency = int((time.perf_counter() - start) * 1000)
        return {
            "model": model,
            "label": label,
            "ok": False,
            "latency_ms": latency,
            "error": str(e)[:80],
        }


async def run_tests(base_url: str, api_key: str, models: list):
    async with httpx.AsyncClient(base_url=base_url) as client:

        # If no key provided, register a new user
        if not api_key:
            api_key = await register_test_user(client)
        else:
            log(f"\n  Using existing API key: {api_key[:20]}...", CYAN)

        log(f"\n{'='*60}", CYAN)
        log(f"  STEP 2 — Testing {len(models)} model(s)", CYAN)
        log(f"  Prompt: \"{TEST_PROMPT}\"", CYAN)
        log(f"{'='*60}", CYAN)

        results = []
        for model, label in models:
            print(f"\n  [{label}] ... ", end="", flush=True)
            result = await test_model(client, api_key, model, label)
            results.append(result)

            if result["ok"]:
                log(f"✅  {result['latency_ms']}ms  →  \"{result['response']}\"", GREEN)
            else:
                log(f"❌  {result['latency_ms']}ms  →  {result['error']}", RED)
                if "detail" in result:
                    log(f"     {result['detail']}", YELLOW)

        # ── Summary ──────────────────────────────────────
        passed = [r for r in results if r["ok"]]
        failed = [r for r in results if not r["ok"]]

        log(f"\n{'='*60}", BOLD)
        log(f"  RESULTS: {len(passed)}/{len(results)} models OK", BOLD)
        log(f"{'='*60}", BOLD)

        if passed:
            log(f"\n  {GREEN}PASSED:{RESET}", BOLD)
            for r in passed:
                log(f"    ✅  {r['label']:<45} {r['latency_ms']}ms")

        if failed:
            log(f"\n  {RED}FAILED:{RESET}", BOLD)
            for r in failed:
                log(f"    ❌  {r['label']:<45} {r['error']}")

        # Check balance after
        try:
            bal_resp = await client.get(
                f"{base_url}/api/user/balance",
                headers={"Authorization": f"Bearer {api_key}"}
            )
            if bal_resp.status_code == 200:
                bal = bal_resp.json()
                log(f"\n  💳 Credits remaining: {bal['credit_balance']:,} ({bal['credits_display']})", CYAN)
        except Exception:
            pass

        log(f"\n{'='*60}\n", CYAN)
        return results


def main():
    parser = argparse.ArgumentParser(description="Test the AI gateway end-to-end")
    parser.add_argument("--base-url", default="http://localhost:4000", help="Gateway base URL")
    parser.add_argument("--key", default=None, help="Use an existing API key (skip registration)")
    parser.add_argument("--model", default=None, help="Test only this model (e.g. gemini-2.0-flash)")
    args = parser.parse_args()

    global BASE_URL
    BASE_URL = args.base_url

    models_to_test = ALL_MODELS
    if args.model:
        models_to_test = [(m, l) for m, l in ALL_MODELS if m == args.model]
        if not models_to_test:
            # Allow freeform model not in list
            models_to_test = [(args.model, args.model)]

    print(f"\n{BOLD}{CYAN}🧪 AI Gateway End-to-End Test{RESET}")
    print(f"   Gateway: {args.base_url}")
    print(f"   Time   : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"   Models : {len(models_to_test)}")

    asyncio.run(run_tests(args.base_url, args.key, models_to_test))


if __name__ == "__main__":
    main()
