#!/usr/bin/env python3
"""
Qwen Account Token Manager
===========================
Retrieves and manages Qwen OAuth tokens for use with the AI gateway.

Qwen's auth is simple: they store a JWT in localStorage on chat.qwen.ai.
We have two ways to get it:

  1. MANUAL (fastest):   You paste the token from your browser dev console.
  2. AUTOMATED (selenium): We open a browser, you log in once, we extract
                           the token from localStorage automatically.

Tokens are stored in:
  - aiclient2api-configs/qwen-accounts.json  (fed to aiclient2api)
  - ./qwen-code-oai-proxy/.env               (if using dedicated proxy)

Usage:
  python scripts/qwen_login.py add            # Add a new account interactively
  python scripts/qwen_login.py list           # List all stored accounts
  python scripts/qwen_login.py validate       # Check which tokens are still valid
  python scripts/qwen_login.py remove <id>    # Remove an account by ID
  python scripts/qwen_login.py export-env     # Print .env additions for proxy
"""
import argparse
import json
import os
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import httpx

# ──────────────────────────────────────────────
# Paths
# ──────────────────────────────────────────────
SCRIPT_DIR = Path(__file__).parent
REPO_ROOT = SCRIPT_DIR.parent

AICLIENT_CONFIGS = REPO_ROOT / "aiclient2api-configs"
QWEN_ACCOUNTS_FILE = REPO_ROOT / "qwen-accounts.json"
QWEN_PROXY_ENV = REPO_ROOT / "qwen-code-oai-proxy" / ".env"

# Qwen's API endpoint used for token validation
QWEN_VALIDATE_URL = "https://chat.qwen.ai/api/v1/accounts/verify"
QWEN_CHAT_URL = "https://chat.qwen.ai/api/chat/completions"

BANNER = """
╔══════════════════════════════════════════════╗
║          Qwen Account Token Manager          ║
║  Get free Qwen3-Coder access via qwen.ai     ║
╚══════════════════════════════════════════════╝
"""


# ──────────────────────────────────────────────
# Storage helpers
# ──────────────────────────────────────────────

def load_accounts() -> list[dict]:
    if QWEN_ACCOUNTS_FILE.exists():
        with open(QWEN_ACCOUNTS_FILE) as f:
            return json.load(f)
    return []


def save_accounts(accounts: list[dict]):
    QWEN_ACCOUNTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(QWEN_ACCOUNTS_FILE, "w") as f:
        json.dump(accounts, f, indent=2)
    print(f"  ✅ Saved {len(accounts)} account(s) to {QWEN_ACCOUNTS_FILE}")


# ──────────────────────────────────────────────
# Token validation
# ──────────────────────────────────────────────

def validate_token(token: str) -> tuple[bool, str]:
    """
    Try a lightweight request to verify the token is still valid.
    Returns (is_valid, message).
    """
    headers = {
        "Authorization": f"Bearer {token}",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "https://chat.qwen.ai/",
        "Origin": "https://chat.qwen.ai",
    }
    try:
        # Use a minimal chat ping to check auth (free tokens work on the basic model)
        resp = httpx.post(
            QWEN_CHAT_URL,
            headers=headers,
            json={
                "model": "qwen-turbo",
                "messages": [{"role": "user", "content": "hi"}],
                "stream": False,
                "max_tokens": 5,
            },
            timeout=15,
        )
        if resp.status_code == 200:
            return True, "✅ Token valid"
        elif resp.status_code == 401:
            return False, "❌ Token expired / invalid (401)"
        elif resp.status_code == 429:
            # Rate limited — the token is valid but quota is hit
            return True, "⚠️  Token valid but rate-limited (429)"
        elif resp.status_code in (502, 503, 504):
            return True, f"⚠️  Server busy ({resp.status_code}). Token likely still valid."
        else:
            return False, f"⚠️  Unexpected status {resp.status_code}: {resp.text[:100]}"
    except httpx.TimeoutException:
        return True, "⚠️  Request timed out. Token likely still valid."
    except httpx.ConnectError:
        return False, "❌ Could not reach chat.qwen.ai"
    except Exception as e:
        return False, f"❌ Error: {e}"


# ──────────────────────────────────────────────
# Commands
# ──────────────────────────────────────────────

def cmd_add(args):
    """Add a new Qwen account token."""
    print(BANNER)
    print("HOW TO GET YOUR TOKEN")
    print("─" * 50)
    print("1. Open https://chat.qwen.ai in your browser")
    print("2. Log in with your Qwen/Alibaba account")
    print("3. Open DevTools (F12) → Console tab")
    print("4. Paste and run this JS snippet:\n")
    print(
        "   javascript:(function(){"
        "const t=localStorage.getItem('token');"
        "if(!t){alert('❌ Not logged in to chat.qwen.ai!');return;}"
        "function copy(text){"
        "  const area=document.createElement('textarea');"
        "  area.value=text;document.body.appendChild(area);"
        "  area.select();"
        "  try{document.execCommand('copy');alert('✅ Token copied to clipboard!');}"
        "  catch(e){prompt('📋 Copy token manually:', text);}"
        "  document.body.removeChild(area);"
        "}"
        "copy(t);"
        "})();\n"
    )
    print("5. Paste the token below. (If the script above fails, you can also run")
    print("   console.log(localStorage.getItem('token')) in the console and copy the result.)\n")
    print("─" * 50)

    token = input("Paste your Qwen token: ").strip()
    if not token:
        print("No token provided. Aborting.")
        sys.exit(1)

    # Strip "Bearer " prefix if accidentally included
    if token.lower().startswith("bearer "):
        token = token[7:].strip()

    print("\nValidating token... ", end="", flush=True)
    is_valid, msg = validate_token(token)
    print(msg)

    if not is_valid and "rate-limited" not in msg:
        ans = input("Token appears invalid. Save anyway? (y/N): ").strip().lower()
        if ans != "y":
            sys.exit(1)

    accounts = load_accounts()
    account_id = input("\nAccount nickname (e.g. 'main', 'account2'): ").strip() or f"qwen-{len(accounts)+1}"
    email = input("Email (optional, for display only): ").strip() or ""

    entry = {
        "id": account_id,
        "token": token,
        "email": email,
        "added_at": datetime.now(timezone.utc).isoformat(),
        "last_validated": datetime.now(timezone.utc).isoformat(),
        "valid": is_valid,
    }

    # Replace if ID exists
    accounts = [a for a in accounts if a["id"] != account_id]
    accounts.append(entry)
    save_accounts(accounts)

    print(f"\n  Account '{account_id}' saved.")
    print("\nNext steps:")
    print("  • To use with aiclient2api:    see 'python scripts/qwen_login.py export-env'")
    print("  • To use with qwen-code-oai-proxy: run 'python scripts/qwen_login.py sync-proxy'")


def cmd_list(args):
    """List stored Qwen accounts."""
    accounts = load_accounts()
    if not accounts:
        print("No Qwen accounts stored. Run: python scripts/qwen_login.py add")
        return

    print(f"\n{'ID':<20} {'Email':<35} {'Added':<25} {'Valid'}")
    print("─" * 95)
    for a in accounts:
        added = a.get("added_at", "unknown")[:19]
        valid = "✅" if a.get("valid") else "❓"
        print(f"{a['id']:<20} {a.get('email',''):<35} {added:<25} {valid}")
    print(f"\nTotal: {len(accounts)} account(s)")


def cmd_validate(args):
    """Re-validate all stored tokens."""
    accounts = load_accounts()
    if not accounts:
        print("No accounts stored.")
        return

    print(f"Validating {len(accounts)} account(s)...\n")
    changed = False
    for a in accounts:
        print(f"  [{a['id']}] ", end="", flush=True)
        is_valid, msg = validate_token(a["token"])
        print(msg)
        was_valid = a.get("valid", None)
        a["valid"] = is_valid
        a["last_validated"] = datetime.now(timezone.utc).isoformat()
        if is_valid != was_valid:
            changed = True

    if changed:
        save_accounts(accounts)
    else:
        print("\nNo changes detected.")


def cmd_remove(args):
    """Remove an account by ID."""
    accounts = load_accounts()
    before = len(accounts)
    accounts = [a for a in accounts if a["id"] != args.account_id]
    if len(accounts) == before:
        print(f"Account '{args.account_id}' not found.")
        sys.exit(1)
    save_accounts(accounts)
    print(f"Removed account '{args.account_id}'.")


def cmd_export_env(args):
    """Print environment variable additions for the qwen-code-oai-proxy."""
    accounts = load_accounts()
    valid_accounts = [a for a in accounts if a.get("valid", True)]

    if not valid_accounts:
        print("No valid accounts found. Run: python scripts/qwen_login.py add")
        return

    print("\n# ── Add to qwen-code-oai-proxy/.env ──")
    print(f"# (Proxy supports up to N accounts via comma separation)")
    print()

    # The qwen-code-oai-proxy uses oauth_creds.json files per account.
    # But it also accepts a single token for simple setups.
    for i, a in enumerate(valid_accounts):
        label = "QWEN_ACCESS_TOKEN" if i == 0 else f"QWEN_ACCESS_TOKEN_{i+1}"
        print(f"{label}={a['token']}")

    print()
    print("# ── To use with aiclient2api (openai-qwen-oauth route) ──")
    print("# The token goes in aiclient2api-configs/qwen-oauth-creds.json")
    print("# Format: { \"access_token\": \"<token>\", \"refresh_token\": \"\" }")
    print()

    if len(valid_accounts) == 1:
        creds = {"access_token": valid_accounts[0]["token"], "refresh_token": ""}
        print("# Single account config for aiclient2api:")
        print(json.dumps(creds, indent=2))
    else:
        print("# Multiple accounts — place each in a separate creds file.")
        for i, a in enumerate(valid_accounts):
            fname = f"qwen-oauth-creds-{a['id']}.json"
            creds = {"access_token": a["token"], "refresh_token": ""}
            print(f"\n# {fname}:")
            print(json.dumps(creds, indent=2))


def cmd_sync_proxy(args):
    """
    Write oauth_creds.json files for the aptdnfapt/qwen-code-oai-proxy.
    Each account gets its own file that the proxy's auth:add command uses.
    """
    accounts = load_accounts()
    valid_accounts = [a for a in accounts if a.get("valid", True)]

    if not valid_accounts:
        print("No valid accounts. Run: python scripts/qwen_login.py add")
        return

    proxy_data_dir = REPO_ROOT / "qwen-code-oai-proxy" / "data"
    proxy_data_dir.mkdir(parents=True, exist_ok=True)

    for a in valid_accounts:
        creds_file = proxy_data_dir / f"oauth_creds_{a['id']}.json"
        creds = {
            "access_token": a["token"],
            "refresh_token": "",
            "account_id": a["id"],
            "email": a.get("email", ""),
        }
        with open(creds_file, "w") as f:
            json.dump(creds, f, indent=2)
        print(f"  Wrote {creds_file}")

    print(f"\n✅ Synced {len(valid_accounts)} account(s) to {proxy_data_dir}")
    print("\nRestart the qwen-code-oai-proxy container to pick up new accounts:")
    print("  docker-compose restart qwen-proxy")


# ──────────────────────────────────────────────
# Entry point
# ──────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Manage Qwen OAuth tokens for the AI gateway",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("add", help="Add a new Qwen account")
    subparsers.add_parser("list", help="List all stored accounts")
    subparsers.add_parser("validate", help="Re-validate all tokens")

    remove_parser = subparsers.add_parser("remove", help="Remove an account")
    remove_parser.add_argument("account_id", help="Account ID to remove")

    subparsers.add_parser("export-env", help="Print .env additions for the proxy")
    subparsers.add_parser("sync-proxy", help="Write creds files for qwen-code-oai-proxy")

    args = parser.parse_args()

    commands = {
        "add": cmd_add,
        "list": cmd_list,
        "validate": cmd_validate,
        "remove": cmd_remove,
        "export-env": cmd_export_env,
        "sync-proxy": cmd_sync_proxy,
    }

    if args.command in commands:
        commands[args.command](args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
