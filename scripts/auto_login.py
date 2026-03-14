#!/usr/bin/env python3
"""
AI Provider Auto-Login (Playwright)
==================================
Automates the capture of OAuth/JWT tokens from browser localStorage.
Supports: Qwen (chat.qwen.ai) and iFlow (iflow.ai).

Requirements:
    pip install playwright httpx
    playwright install chromium
"""
import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
except ImportError:
    print("❌ Playwright not found. Run: pip install playwright && playwright install chromium")
    sys.exit(1)

try:
    from playwright_stealth import stealth_async
except ImportError:
    stealth_async = None  # Optional — works without it but Google may block

import httpx

# ──────────────────────────────────────────────
# Paths
# ──────────────────────────────────────────────
REPO_ROOT = Path(__file__).parent.parent
QWEN_FILE = REPO_ROOT / "qwen-accounts.json"
IFLOW_FILE = REPO_ROOT / "iflow-accounts.json"

# API Endpoints for validation
QWEN_CHAT_URL = "https://chat.qwen.ai/api/chat/completions"
IFLOW_MODELS_URL = "https://iflow.cn/api/models"

BANNER = """
╔══════════════════════════════════════════════╗
║         AI PROVIDER AUTO-LOGIN TOOL          ║
║     Automated Token Capture via Browser      ║
╚══════════════════════════════════════════════╝
"""

# ──────────────────────────────────────────────
# Validation Logic (Shared with manual scripts)
# ──────────────────────────────────────────────

async def validate_qwen(token: str) -> tuple[bool, str]:
    headers = {
        "Authorization": f"Bearer {token}",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    }
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(
                QWEN_CHAT_URL,
                headers=headers,
                json={"model": "qwen-turbo", "messages": [{"role": "user", "content": "hi"}], "stream": False, "max_tokens": 5},
                timeout=10,
            )
            if resp.status_code == 200: return True, "✅ Token valid"
            if resp.status_code == 401: return False, "❌ Token expired/invalid"
            if resp.status_code in (502, 503, 504): return True, f"⚠️ Server busy ({resp.status_code}), likely valid"
            return False, f"⚠️ Status {resp.status_code}"
        except Exception as e:
            return True, f"⚠️ Validation timeout/error, likely valid ({str(e)})"

async def validate_iflow(token: str) -> tuple[bool, str]:
    headers = {"Authorization": f"Bearer {token}"}
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(IFLOW_MODELS_URL, headers=headers, timeout=10)
            if resp.status_code == 200: return True, "✅ Token valid"
            if resp.status_code == 401: return False, "❌ Token expired/invalid"
            return False, f"⚠️ Status {resp.status_code}"
        except Exception:
            return True, "⚠️ Validation timeout, likely valid"

# ──────────────────────────────────────────────
# Browser Automation
# ──────────────────────────────────────────────

async def capture_token(url: str, storage_key: str, provider_name: str):
    """Opens Chrome with the user's real profile, waits for login, sniffs localStorage."""
    print(f"\n🚀 Capturing {provider_name} token...")
    print(f"   Opening {url} ...")
    print("   PLEASE LOG IN IN THE BROWSER WINDOW.")

    # Use the real Chrome profile → Google sees your existing session, not a bot
    chrome_profile = os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\User Data")

    async with async_playwright() as p:
        try:
            # launch_persistent_context opens Chrome with your actual profile,
            # so Google/Qwen/iFlow already consider you "trusted".
            context = await p.chromium.launch_persistent_context(
                user_data_dir=chrome_profile,
                channel="chrome",
                headless=False,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-first-run",
                    "--no-default-browser-check",
                ],
            )
            print("   (Using your existing Chrome profile — Google login should work)")
        except Exception as e:
            print(f"   ⚠️  Could not open Chrome profile: {e}")
            print("   Falling back to a fresh browser (OAuth may be blocked)...")
            browser = await p.chromium.launch(headless=False)
            context = await browser.new_context()

        page = await context.new_page()

        # Apply stealth patches to hide automation signals from the page
        if stealth_async:
            await stealth_async(page)

        print()
        print("   ⚠️  IMPORTANT: Do NOT use the 'Sign in with Google' button!")
        print("   Use email/phone + password login instead (Google blocks automated browsers).")
        print("   Qwen: use 'Sign in with phone/email' or scan QR with Alibaba app.")
        print()

        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        except Exception as e:
            print(f"   ⚠️  Navigation warning (ok to ignore): {e}")

        print(f"   Watching localStorage for '{storage_key}'...")
        print("   Log in now — window will close automatically once token is captured.")

        token = None
        start_time = datetime.now()

        while True:
            try:
                token = await page.evaluate(f"localStorage.getItem('{storage_key}')")
                # iFlow may store under a different key
                if not token and provider_name == "iFlow":
                    token = await page.evaluate("localStorage.getItem('access_token')")
            except Exception:
                # Mid-navigation redirect — completely normal during login
                await asyncio.sleep(1)
                continue

            if token:
                print(f"   ✅ {provider_name} token captured!")
                await asyncio.sleep(0.5)
                break

            if (datetime.now() - start_time).total_seconds() > 300:
                print("   ❌ Timeout (5 min). Try the manual script instead.")
                break

            await asyncio.sleep(1)

        await context.close()
        return token

# ──────────────────────────────────────────────
# Main Application
# ──────────────────────────────────────────────

async def save_account(file_path: Path, account_id: str, token: str, is_valid: bool, email: str = ""):
    accounts = []
    if file_path.exists():
        with open(file_path) as f:
            accounts = json.load(f)
    
    new_entry = {
        "id": account_id,
        "token": token,
        "email": email,
        "added_at": datetime.now(timezone.utc).isoformat(),
        "last_validated": datetime.now(timezone.utc).isoformat(),
        "valid": is_valid,
        "method": "auto-playwright"
    }
    
    # Update or append
    accounts = [a for a in accounts if a["id"] != account_id]
    accounts.append(new_entry)
    
    with open(file_path, "w") as f:
        json.dump(accounts, f, indent=2)
    print(f"   📝 Saved to {file_path.name}")

async def run_qwen_flow():
    token = await capture_token("https://chat.qwen.ai", "token", "Qwen")
    if token:
        valid, msg = await validate_qwen(token)
        print(f"   {msg}")
        
        # Get metadata
        nick = input("\n   Account Nickname (e.g. main): ").strip() or "qwen-auto"
        email = input("   Account Email (optional): ").strip()
        await save_account(QWEN_FILE, nick, token, valid, email)
        
        # Propose sync
        print(f"\n   💡 Run 'python scripts/qwen_login.py sync-proxy' to update services.")

async def run_iflow_flow():
    # iFlow's main service lives at iflow.cn (the .ai domain is their CLI repo/docs)
    token = await capture_token("https://iflow.cn", "token", "iFlow")
    if token:
        valid, msg = await validate_iflow(token)
        print(f"   {msg}")

        nick = input("\n   Account Nickname (e.g. main): ").strip() or "iflow-auto"
        email = input("   Account Email (optional): ").strip()
        await save_account(IFLOW_FILE, nick, token, valid, email)

        print(f"\n   💡 Run 'python scripts/iflow_login.py sync-proxy' to update services.")

async def main():
    print(BANNER)
    print("1. Qwen (chat.qwen.ai)")
    print("2. iFlow (iflow.cn)")
    print("3. Both")
    print("q. Quit")
    
    choice = input("\nSelect provider to automate: ").strip().lower()
    
    if choice == '1':
        await run_qwen_flow()
    elif choice == '2':
        await run_iflow_flow()
    elif choice == '3':
        await run_qwen_flow()
        await run_iflow_flow()
    elif choice == 'q':
        return
    else:
        print("Invalid choice.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Cancelled.")
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
