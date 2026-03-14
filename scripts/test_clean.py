import json, time, httpx, uuid, asyncio

BASE_URL = "http://localhost:4000"
PROMPT = "Reply with exactly the word: OK"

MODELS = {
    "openai": [
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
    ],
    "anthropic": [
        ("claude-sonnet-4-5",       "Claude Sonnet 4.5 (Kiro) [Anthropic fmt]"),
        ("claude-opus-4-5",         "Claude Opus 4.5 (Kiro) [Anthropic fmt]"),
        ("gemini-2.0-flash",        "Gemini 2.0 Flash (Antigravity) [Anthropic fmt]"),
        ("copilot-claude-sonnet",   "Claude Sonnet (Copilot) [Anthropic fmt]"),
    ],
    "gemini": [
        ("gemini-2.0-flash",        "Gemini 2.0 Flash (Antigravity) [Gemini fmt]"),
        ("gemini-2.5-pro",          "Gemini 2.5 Pro (Antigravity) [Gemini fmt]"),
        ("gemini-2.5-flash",        "Gemini 2.5 Flash (Antigravity) [Gemini fmt]"),
    ]
}

async def run():
    async with httpx.AsyncClient() as client:
        # 1. register
        uid = uuid.uuid4().hex[:8]
        r = await client.post(f"{BASE_URL}/api/auth/register", json={
            "email": f"test-{uid}@test.local", "password": "pass", "display_name": "test"
        })
        key = r.json()["api_key"]
        print(f"Key registered: {key}")

        results = []

        # OpenAI
        for m, lbl in MODELS["openai"]:
            t0 = time.time()
            try:
                rx = await client.post(
                    f"{BASE_URL}/v1/chat/completions",
                    headers={"Authorization": f"Bearer {key}"},
                    json={"model": m, "messages": [{"role": "user", "content": PROMPT}], "max_tokens": 20},
                    timeout=50
                )
                ms = int((time.time() - t0) * 1000)
                if rx.status_code == 200:
                    d = rx.json()
                    results.append({"fmt": "openai", "model": m, "label": lbl, "ok": True, "ms": ms, "reply": d["choices"][0]["message"]["content"]})
                else:
                    results.append({"fmt": "openai", "model": m, "label": lbl, "ok": False, "ms": ms, "error": f"HTTP {rx.status_code}", "raw": rx.text[:100]})
            except Exception as e:
                results.append({"fmt": "openai", "model": m, "label": lbl, "ok": False, "ms": int((time.time() - t0)*1000), "error": str(e)})

        # Anthropic
        for m, lbl in MODELS["anthropic"]:
            t0 = time.time()
            try:
                rx = await client.post(
                    f"{BASE_URL}/v1/messages",
                    headers={"Authorization": f"Bearer {key}", "x-api-key": key, "anthropic-version": "2023-06-01"},
                    json={"model": m, "messages": [{"role": "user", "content": PROMPT}], "max_tokens": 20},
                    timeout=50
                )
                ms = int((time.time() - t0) * 1000)
                if rx.status_code == 200:
                    d = rx.json()
                    txt = next((b["text"] for b in d.get("content", []) if b.get("type") == "text"), "")
                    results.append({"fmt": "anthropic", "model": m, "label": lbl, "ok": True, "ms": ms, "reply": txt})
                else:
                    results.append({"fmt": "anthropic", "model": m, "label": lbl, "ok": False, "ms": ms, "error": f"HTTP {rx.status_code}", "raw": rx.text[:100]})
            except Exception as e:
                results.append({"fmt": "anthropic", "model": m, "label": lbl, "ok": False, "ms": int((time.time() - t0)*1000), "error": str(e)})

        # Gemini
        for m, lbl in MODELS["gemini"]:
            t0 = time.time()
            try:
                rx = await client.post(
                    f"{BASE_URL}/v1beta/models/{m}:generateContent",
                    headers={"Authorization": f"Bearer {key}"},
                    json={"contents": [{"role": "user", "parts": [{"text": PROMPT}]}], "generationConfig": {"maxOutputTokens": 20}},
                    timeout=50
                )
                ms = int((time.time() - t0) * 1000)
                if rx.status_code == 200:
                    d = rx.json()
                    txt = d["candidates"][0]["content"]["parts"][0]["text"]
                    results.append({"fmt": "gemini", "model": m, "label": lbl, "ok": True, "ms": ms, "reply": txt})
                else:
                    results.append({"fmt": "gemini", "model": m, "label": lbl, "ok": False, "ms": ms, "error": f"HTTP {rx.status_code}", "raw": rx.text[:100]})
            except Exception as e:
                results.append({"fmt": "gemini", "model": m, "label": lbl, "ok": False, "ms": int((time.time() - t0)*1000), "error": str(e)})

        # Print cleanly
        print("\n--- RESULTS ---")
        for r in results:
            if r["ok"]:
                print(f"PASS | {r['fmt']:9} | {r['ms']:5}ms | {r['label']:45} | {r['reply'][:30].strip()}")
            else:
                print(f"FAIL | {r['fmt']:9} | {r['ms']:5}ms | {r['label']:45} | {r['error']}  ({r.get('raw', '')})")

if __name__ == "__main__":
    asyncio.run(run())
