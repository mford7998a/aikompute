#!/usr/bin/env python3
"""
Multi-Format Gateway Test
=========================
Tests all 3 API formats for all models:
  1. OpenAI   → POST /v1/chat/completions
  2. Anthropic → POST /v1/messages
  3. Gemini   → POST /v1beta/models/{model}:generateContent

Usage:
  python scripts/test_all_formats.py
  python scripts/test_all_formats.py --key sk-inf-xxxx
  python scripts/test_all_formats.py --format openai
  python scripts/test_all_formats.py --format claude
  python scripts/test_all_formats.py --format gemini
"""
import argparse
import asyncio
import sys
import time
import uuid
import json
from datetime import datetime

import httpx

BASE_URL = "http://localhost:4000"
PROMPT = "Reply with exactly the word: OK"

# ─── Models by category ───────────────────────────────────────────────────────
OPENAI_MODELS = [
    ("gemini-2.0-flash",        "Gemini 2.0 Flash (Antigravity)"),
    ("gemini-2.5-pro",          "Gemini 2.5 Pro (Antigravity)"),
    ("gemini-2.5-flash",        "Gemini 2.5 Flash (Antigravity)"),
    ("claude-sonnet-4-5",       "Claude Sonnet 4.5 (Kiro)"),
    ("claude-opus-4-5",         "Claude Opus 4.5 (Kiro)"),
    ("qwen-turbo",              "Qwen Turbo (Qwen)"),
    ("qwen3-coder",             "Qwen3 Coder (Qwen)"),
    ("qwen3-coder-plus",        "Qwen3 Coder Plus (Qwen)"),
    ("github-gpt-4o",           "GPT-4o (GitHub Models)"),
    ("github-gpt-4.1",          "GPT-4.1 (GitHub Models)"),
    ("github-o4-mini",          "o4-mini (GitHub Models)"),
    ("github-claude-sonnet",    "Claude Sonnet (GitHub Models)"),
    ("github-gemini-pro",       "Gemini Pro (GitHub Models)"),
    ("github-deepseek-v3",      "DeepSeek V3 (GitHub Models)"),
    ("copilot-gpt-4o",          "GPT-4o (Copilot)"),
    ("copilot-gpt-4.1",         "GPT-4.1 (Copilot)"),
    ("copilot-o4-mini",         "o4-mini (Copilot)"),
    ("copilot-claude-sonnet",   "Claude Sonnet (Copilot)"),
    ("trae-gpt-4o",             "GPT-4o (Trae)"),
]

# Anthropic format: only Claude models make sense (though gateway translates all)
CLAUDE_MODELS = [
    ("claude-sonnet-4-5",       "Claude Sonnet 4.5 (Kiro) [Anthropic fmt]"),
    ("claude-opus-4-5",         "Claude Opus 4.5 (Kiro) [Anthropic fmt]"),
    ("gemini-2.0-flash",        "Gemini 2.0 Flash (Antigravity) [Anthropic fmt]"),
    ("copilot-claude-sonnet",   "Claude Sonnet (Copilot) [Anthropic fmt]"),
]

# Gemini format: only Gemini models make sense (though gateway translates all)
GEMINI_MODELS = [
    ("gemini-2.0-flash",        "Gemini 2.0 Flash (Antigravity) [Gemini fmt]"),
    ("gemini-2.5-pro",          "Gemini 2.5 Pro (Antigravity) [Gemini fmt]"),
    ("gemini-2.5-flash",        "Gemini 2.5 Flash (Antigravity) [Gemini fmt]"),
]

# ─── ANSI colours ────────────────────────────────────────────────────────────
G = "\033[92m"; R = "\033[91m"; Y = "\033[93m"
C = "\033[96m"; B = "\033[1m";  RST = "\033[0m"


def pr(msg, col=""):
    print(f"{col}{msg}{RST}", flush=True)


# ─── Auth ────────────────────────────────────────────────────────────────────

async def get_api_key(client: httpx.AsyncClient, base_url: str) -> str:
    uid = uuid.uuid4().hex[:8]
    email = f"fmt-test-{uid}@test.local"
    resp = await client.post(f"{base_url}/api/auth/register", json={
        "email": email, "password": "TestP@ssw0rd!", "display_name": f"FmtTest {uid}"
    }, timeout=15)
    if resp.status_code != 200:
        pr(f"Registration failed: {resp.status_code} {resp.text}", R)
        sys.exit(1)
    d = resp.json()
    pr(f"  ✅ Registered: {email}", G)
    pr(f"  🔑 Key: {d['api_key']}", G)
    pr(f"  💳 Credits: {d.get('credit_balance', 0):,}", G)
    return d["api_key"]


# ─── Test functions ──────────────────────────────────────────────────────────

async def test_openai(client: httpx.AsyncClient, base_url: str, key: str, model: str, label: str) -> dict:
    """Test via OpenAI /v1/chat/completions format."""
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": PROMPT}],
        "max_tokens": 20,
        "stream": False,
    }
    t0 = time.perf_counter()
    try:
        r = await client.post(f"{base_url}/v1/chat/completions", json=payload, headers=headers, timeout=50)
        ms = int((time.perf_counter() - t0) * 1000)
        if r.status_code == 200:
            d = r.json()
            choices = d.get("choices", [])
            if not choices:
                return {"ok": False, "ms": ms, "label": label, "model": model, "fmt": "openai",
                        "err": "no 'choices' in response", "raw": str(d)[:120]}
            content = choices[0].get("message", {}).get("content", "").strip()
            return {"ok": True, "ms": ms, "label": label, "model": model, "fmt": "openai",
                    "reply": content[:60]}
        else:
            return {"ok": False, "ms": ms, "label": label, "model": model, "fmt": "openai",
                    "err": f"HTTP {r.status_code}", "raw": r.text[:120]}
    except httpx.TimeoutException:
        return {"ok": False, "ms": int((time.perf_counter()-t0)*1000), "label": label, "model": model,
                "fmt": "openai", "err": "TIMEOUT >50s"}
    except Exception as e:
        return {"ok": False, "ms": int((time.perf_counter()-t0)*1000), "label": label, "model": model,
                "fmt": "openai", "err": str(e)[:80]}


async def test_anthropic(client: httpx.AsyncClient, base_url: str, key: str, model: str, label: str) -> dict:
    """Test via Anthropic /v1/messages format."""
    headers = {
        "Authorization": f"Bearer {key}",
        "x-api-key": key,
        "anthropic-version": "2023-06-01",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "max_tokens": 20,
        "messages": [{"role": "user", "content": PROMPT}],
    }
    t0 = time.perf_counter()
    try:
        r = await client.post(f"{base_url}/v1/messages", json=payload, headers=headers, timeout=50)
        ms = int((time.perf_counter() - t0) * 1000)
        if r.status_code == 200:
            d = r.json()
            # Anthropic format: {"content": [{"type": "text", "text": "..."}]}
            content_blocks = d.get("content", [])
            if not content_blocks:
                return {"ok": False, "ms": ms, "label": label, "model": model, "fmt": "anthropic",
                        "err": "no 'content' in response", "raw": str(d)[:120]}
            text = next((b.get("text","") for b in content_blocks if b.get("type")=="text"), "")
            return {"ok": True, "ms": ms, "label": label, "model": model, "fmt": "anthropic",
                    "reply": text.strip()[:60]}
        else:
            return {"ok": False, "ms": ms, "label": label, "model": model, "fmt": "anthropic",
                    "err": f"HTTP {r.status_code}", "raw": r.text[:120]}
    except httpx.TimeoutException:
        return {"ok": False, "ms": int((time.perf_counter()-t0)*1000), "label": label, "model": model,
                "fmt": "anthropic", "err": "TIMEOUT >50s"}
    except Exception as e:
        return {"ok": False, "ms": int((time.perf_counter()-t0)*1000), "label": label, "model": model,
                "fmt": "anthropic", "err": str(e)[:80]}


async def test_gemini(client: httpx.AsyncClient, base_url: str, key: str, model: str, label: str) -> dict:
    """Test via Gemini /v1beta/models/{model}:generateContent format."""
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }
    payload = {
        "contents": [{"role": "user", "parts": [{"text": PROMPT}]}],
        "generationConfig": {"maxOutputTokens": 20},
    }
    url = f"{base_url}/v1beta/models/{model}:generateContent"
    t0 = time.perf_counter()
    try:
        r = await client.post(url, json=payload, headers=headers, timeout=50)
        ms = int((time.perf_counter() - t0) * 1000)
        if r.status_code == 200:
            d = r.json()
            # Gemini format: {"candidates": [{"content": {"parts": [{"text": "..."}]}}]}
            candidates = d.get("candidates", [])
            if not candidates:
                return {"ok": False, "ms": ms, "label": label, "model": model, "fmt": "gemini",
                        "err": "no 'candidates' in response", "raw": str(d)[:120]}
            parts = candidates[0].get("content", {}).get("parts", [])
            text = next((p.get("text","") for p in parts if "text" in p), "")
            return {"ok": True, "ms": ms, "label": label, "model": model, "fmt": "gemini",
                    "reply": text.strip()[:60]}
        else:
            return {"ok": False, "ms": ms, "label": label, "model": model, "fmt": "gemini",
                    "err": f"HTTP {r.status_code}", "raw": r.text[:120]}
    except httpx.TimeoutException:
        return {"ok": False, "ms": int((time.perf_counter()-t0)*1000), "label": label, "model": model,
                "fmt": "gemini", "err": "TIMEOUT >50s"}
    except Exception as e:
        return {"ok": False, "ms": int((time.perf_counter()-t0)*1000), "label": label, "model": model,
                "fmt": "gemini", "err": str(e)[:80]}


# ─── Runner ──────────────────────────────────────────────────────────────────

SECTION_WIDTH = 68

def section(title: str, color=C):
    pr(f"\n{'='*SECTION_WIDTH}", color)
    pr(f"  {title}", color)
    pr(f"{'='*SECTION_WIDTH}", color)


def print_row(result: dict):
    label = result["label"]
    if result["ok"]:
        reply = result.get("reply", "")
        pr(f"    {G}✅{RST}  {label:<50} {result['ms']:>5}ms  → \"{reply}\"")
    else:
        err = result.get("err", "?")
        raw = result.get("raw", "")
        pr(f"    {R}❌{RST}  {label:<50} {result['ms']:>5}ms  → {err}")
        if raw:
            pr(f"         {Y}{raw}{RST}")


def print_summary(results: list, fmt_name: str):
    passed = [r for r in results if r["ok"]]
    failed = [r for r in results if not r["ok"]]
    color = G if not failed else (Y if passed else R)
    pr(f"\n  {B}[ {fmt_name} ]  {len(passed)}/{len(results)} passed{RST}", color)
    return passed, failed


async def run_format(
    client: httpx.AsyncClient, base_url: str, key: str,
    fmt: str, models: list
) -> list:
    results = []
    for model, label in models:
        print(f"  {'⬜'} {label:<55}", end="", flush=True)
        if fmt == "openai":
            r = await test_openai(client, base_url, key, model, label)
        elif fmt == "anthropic":
            r = await test_anthropic(client, base_url, key, model, label)
        elif fmt == "gemini":
            r = await test_gemini(client, base_url, key, model, label)
        # Move cursor back and overwrite
        print(f"\r", end="")
        print_row(r)
        results.append(r)
    return results


async def main_async(base_url: str, key: str | None, only_fmt: str | None):
    async with httpx.AsyncClient() as client:

        # -- Auth --
        section("STEP 1 — Getting API key")
        if key:
            pr(f"  Using provided key: {key[:20]}...", C)
        else:
            key = await get_api_key(client, base_url)

        all_results = []

        # ── OpenAI format ─────────────────────────────────────────────────
        if not only_fmt or only_fmt == "openai":
            section("STEP 2 — OpenAI format  (POST /v1/chat/completions)")
            pr(f"  Testing {len(OPENAI_MODELS)} models...\n")
            res = await run_format(client, base_url, key, "openai", OPENAI_MODELS)
            all_results.extend(res)
            print_summary(res, "OpenAI /v1/chat/completions")

        # ── Anthropic format ──────────────────────────────────────────────
        if not only_fmt or only_fmt == "claude":
            section("STEP 3 — Anthropic format  (POST /v1/messages)")
            pr(f"  Testing {len(CLAUDE_MODELS)} models...\n")
            res = await run_format(client, base_url, key, "anthropic", CLAUDE_MODELS)
            all_results.extend(res)
            print_summary(res, "Anthropic /v1/messages")

        # ── Gemini format ─────────────────────────────────────────────────
        if not only_fmt or only_fmt == "gemini":
            section("STEP 4 — Gemini format  (POST /v1beta/models/{model}:generateContent)")
            pr(f"  Testing {len(GEMINI_MODELS)} models...\n")
            res = await run_format(client, base_url, key, "gemini", GEMINI_MODELS)
            all_results.extend(res)
            print_summary(res, "Gemini /v1beta generateContent")

        # ── Grand summary ─────────────────────────────────────────────────
        section("OVERALL RESULTS", B)
        passed = [r for r in all_results if r["ok"]]
        failed = [r for r in all_results if not r["ok"]]
        pr(f"\n  {B}{G}PASSED ({len(passed)}/{len(all_results)}):{RST}")
        for r in passed:
            pr(f"    ✅  [{r['fmt'].upper():<9}]  {r['label']}")

        if failed:
            pr(f"\n  {B}{R}FAILED ({len(failed)}/{len(all_results)}):{RST}")
            for r in failed:
                pr(f"    ❌  [{r['fmt'].upper():<9}]  {r['label']:<50}  → {r.get('err','?')}")

        pr(f"\n  Ran at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        pr(f"  Gateway: {base_url}\n")

        # -- Final balance --
        try:
            b = await client.get(f"{base_url}/api/user/balance",
                                  headers={"Authorization": f"Bearer {key}"}, timeout=5)
            if b.status_code == 200:
                bd = b.json()
                pr(f"  💳 Credits remaining: {bd['credit_balance']:,}  ({bd.get('credits_display','')})\n", C)
        except Exception:
            pass

        pr("=" * SECTION_WIDTH + "\n", C)


def main():
    parser = argparse.ArgumentParser(description="Test all 3 API formats against the gateway")
    parser.add_argument("--base-url", default="http://localhost:4000")
    parser.add_argument("--key", default=None, help="Existing API key (skip registration)")
    parser.add_argument("--format", default=None, choices=["openai", "claude", "gemini"],
                        help="Test only one format")
    args = parser.parse_args()

    pr(f"\n{B}{C}🧪 Multi-Format Gateway Test{RST}")
    pr(f"   Gateway : {args.base_url}")
    pr(f"   Format  : {args.format or 'ALL (openai + claude + gemini)'}")
    pr(f"   Time    : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    asyncio.run(main_async(args.base_url, args.key, args.format))


if __name__ == "__main__":
    main()
