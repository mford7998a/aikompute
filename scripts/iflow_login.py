#!/usr/bin/env python3
"""
iFlow Account Token Manager
=============================
Retrieves and manages iFlow OAuth tokens for use with the AI gateway.

iFlow is an AI service at iflow.ai (powered by GLM/ZhipuAI models).
Their CLI (iflow-ai/iflow-cli) uses OAuth and stores creds in:
  ~/.iflow/settings.json   or   oauth_creds.json

We support two strategies:
  1. MANUAL TOKEN:   You grab the token from browser DevTools
  2. CLI-ASSISTED:   If you have iflow-cli installed, we call `iflow auth`
                     for you and harvest the generated creds file

Tokens are then stored in:
  - iflow-accounts.json          (our local registry)
  - iflow2api/.env               (for rtiy1/iflow2api Docker service)

Usage:
  python scripts/iflow_login.py add            # Add a new account
  python scripts/iflow_login.py add --cli      # Use iflow-cli auth flow
  python scripts/iflow_login.py list           # List all accounts
  python scripts/iflow_login.py validate       # Check token validity
  python scripts/iflow_login.py remove <id>    # Remove an account
  python scripts/iflow_login.py sync-proxy     # Write creds for iflow2api
  python scripts/iflow_login.py export-env     # Print env var additions
"""
import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import httpx

# ──────────────────────────────────────────────
# Paths
# ──────────────────────────────────────────────
SCRIPT_DIR = Path(__file__).parent
REPO_ROOT = SCRIPT_DIR.parent

IFLOW_ACCOUNTS_FILE = REPO_ROOT / "iflow-accounts.json"
IFLOW2API_DIR = REPO_ROOT / "iflow2api"
IFLOW_HOME = Path.home() / ".iflow"
IFLOW_CREDS_FILE = IFLOW_HOME / "oauth_creds.json"
IFLOW_SETTINGS_FILE = IFLOW_HOME / "settings.json"

# iFlow API endpoints (reverse-engineered from iflow-cli + rtiy1/iflow2api)
IFLOW_API_BASE = "https://iflow.ai"
IFLOW_CHAT_URL = f"{IFLOW_API_BASE}/api/chat/completions"
IFLOW_MODELS_URL = f"{IFLOW_API_BASE}/api/models"

BANNER = """
╔══════════════════════════════════════════════╗
║          iFlow Account Token Manager         ║
║   Get free GLM/ZhipuAI access via iFlow      ║
╚══════════════════════════════════════════════╝
"""

BROWSER_INSTRUCTIONS = r"""
HOW TO GET YOUR iFlow TOKEN (manual method)
──────────────────────────────────────────────
1. Go to https://iflow.ai and sign in
2. Open DevTools (F12) → Console tab
3. Paste and run this JS snippet:

   javascript:(function(){
     const t=localStorage.getItem('token')||localStorage.getItem('access_token');
     if(!t){alert('❌ Not logged in to iflow.ai!');return;}
     function copy(text){
       const area=document.createElement('textarea');
       area.value=text;document.body.appendChild(area);
       area.select();
       try{document.execCommand('copy');alert('✅ Token copied to clipboard!');}
       catch(e){prompt('📋 Copy token manually:', text);}
       document.body.removeChild(area);
     }
     copy(t);
   })();

4. Paste the output below (or just copy the 'Authorization' header from Network tab)
──────────────────────────────────────────────
"""


# ──────────────────────────────────────────────
# Storage
# ──────────────────────────────────────────────

def load_accounts() -> list[dict]:
    if IFLOW_ACCOUNTS_FILE.exists():
        with open(IFLOW_ACCOUNTS_FILE) as f:
            return json.load(f)
    return []


def save_accounts(accounts: list[dict]):
    with open(IFLOW_ACCOUNTS_FILE, "w") as f:
        json.dump(accounts, f, indent=2)
    print(f"  ✅ Saved {len(accounts)} account(s) to {IFLOW_ACCOUNTS_FILE}")


# ──────────────────────────────────────────────
# Token validation
# ──────────────────────────────────────────────

def validate_token(token: str) -> tuple[bool, str]:
    """
    Validate an iFlow token by hitting the models endpoint.
    Returns (is_valid, message).
    """
    headers = {
        "Authorization": f"Bearer {token}",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Referer": "https://iflow.ai/",
        "Origin": "https://iflow.ai",
        "Content-Type": "application/json",
    }
    try:
        # Try the models endpoint first (lightweight)
        resp = httpx.get(IFLOW_MODELS_URL, headers=headers, timeout=10)
        if resp.status_code == 200:
            return True, "✅ Token valid"
        elif resp.status_code == 401:
            return False, "❌ Token expired / invalid (401)"
        elif resp.status_code == 403:
            return False, "❌ Token forbidden (403)"
        elif resp.status_code == 429:
            return True, "⚠️  Token valid but rate-limited (429)"

        # Fallback: try a minimal chat completion
        chat_resp = httpx.post(
            IFLOW_CHAT_URL,
            headers=headers,
            json={
                "model": "glm-4-flash",
                "messages": [{"role": "user", "content": "hi"}],
                "stream": False,
                "max_tokens": 5,
            },
            timeout=15,
        )
        if chat_resp.status_code == 200:
            return True, "✅ Token valid (via chat endpoint)"
        elif chat_resp.status_code == 401:
            return False, "❌ Token expired / invalid"
        elif chat_resp.status_code in (502, 503, 504):
            return True, f"⚠️  Server busy ({chat_resp.status_code}). Token likely still valid."
        else:
            return False, f"⚠️  Status {chat_resp.status_code}: {chat_resp.text[:100]}"

    except httpx.TimeoutException:
        return True, "⚠️  Request timed out. Token likely still valid."
    except httpx.ConnectError:
        return False, "❌ Could not reach iflow.ai — check your connection"
    except Exception as e:
        return False, f"❌ Validation error: {e}"


# ──────────────────────────────────────────────
# CLI-assisted auth
# ──────────────────────────────────────────────

def run_iflow_cli_auth() -> str | None:
    """
    Run `iflow auth` (from @iflow-ai/cli) and harvest the resulting creds file.
    Returns the access_token if successful, None otherwise.
    """
    print("Launching iflow-cli auth flow...")
    print("(A browser window will open. Log in, then return here.)\n")

    try:
        result = subprocess.run(
            ["iflow", "auth"],
            check=False,
            capture_output=False,  # Let it print to terminal (user needs to see browser link)
            timeout=120,
        )
    except FileNotFoundError:
        print("❌ 'iflow' command not found.")
        print("   Install it with: npm install -g @iflow-ai/cli")
        return None
    except subprocess.TimeoutExpired:
        print("⏱️  Auth timed out (120s). Try the manual method instead.")
        return None

    # Read the generated creds file
    for creds_path in [IFLOW_CREDS_FILE, IFLOW_SETTINGS_FILE]:
        if creds_path.exists():
            with open(creds_path) as f:
                data = json.load(f)
            token = data.get("access_token") or data.get("token") or data.get("api_key")
            if token:
                print(f"✅ Found token in {creds_path}")
                return token

    print("⚠️  Could not find token in ~/.iflow/ after auth.")
    print(f"   Expected: {IFLOW_CREDS_FILE} or {IFLOW_SETTINGS_FILE}")
    return None


# ──────────────────────────────────────────────
# Commands
# ──────────────────────────────────────────────

def cmd_add(args):
    """Add a new iFlow account."""
    print(BANNER)

    token = None

    if getattr(args, "cli", False):
        token = run_iflow_cli_auth()

    if not token:
        print(BROWSER_INSTRUCTIONS)
        token = input("Paste your iFlow token: ").strip()
        if not token:
            print("No token provided. Aborting.")
            sys.exit(1)

    # Strip "Bearer " prefix
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
    default_id = f"iflow-{len(accounts)+1}"
    account_id = input(f"\nAccount nickname [{default_id}]: ").strip() or default_id
    email = input("Email (optional, for display only): ").strip() or ""

    entry = {
        "id": account_id,
        "token": token,
        "email": email,
        "added_at": datetime.now(timezone.utc).isoformat(),
        "last_validated": datetime.now(timezone.utc).isoformat(),
        "valid": is_valid,
    }

    accounts = [a for a in accounts if a["id"] != account_id]
    accounts.append(entry)
    save_accounts(accounts)

    print(f"\n  ✅ Account '{account_id}' saved.")
    print("\nNext steps:")
    print("  python scripts/iflow_login.py sync-proxy   # Set up iflow2api container")
    print("  python scripts/iflow_login.py export-env   # See env vars to add")


def cmd_list(args):
    accounts = load_accounts()
    if not accounts:
        print("No iFlow accounts stored. Run: python scripts/iflow_login.py add")
        return
    print(f"\n{'ID':<20} {'Email':<35} {'Added':<25} {'Valid'}")
    print("─" * 95)
    for a in accounts:
        added = a.get("added_at", "unknown")[:19]
        valid = "✅" if a.get("valid") else "❓"
        print(f"{a['id']:<20} {a.get('email',''):<35} {added:<25} {valid}")
    print(f"\nTotal: {len(accounts)} account(s)")


def cmd_validate(args):
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
        if is_valid != a.get("valid"):
            changed = True
        a["valid"] = is_valid
        a["last_validated"] = datetime.now(timezone.utc).isoformat()
    if changed:
        save_accounts(accounts)


def cmd_remove(args):
    accounts = load_accounts()
    before = len(accounts)
    accounts = [a for a in accounts if a["id"] != args.account_id]
    if len(accounts) == before:
        print(f"Account '{args.account_id}' not found.")
        sys.exit(1)
    save_accounts(accounts)
    print(f"Removed account '{args.account_id}'.")


def cmd_sync_proxy(args):
    """
    Write the settings.json / oauth_creds.json files consumed by rtiy1/iflow2api.
    
    iflow2api reads from ~/.iflow/settings.json (when running locally)
    or from a mounted volume path when in Docker.
    We write to ./iflow2api/data/ which gets volume-mounted into the container.
    """
    accounts = load_accounts()
    valid_accounts = [a for a in accounts if a.get("valid", True)]

    if not valid_accounts:
        print("No valid accounts. Run: python scripts/iflow_login.py add")
        return

    data_dir = IFLOW2API_DIR / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    # iflow2api reads a primary settings.json then falls back to oauth_creds.json
    # Use the first (primary) account as the main settings
    primary = valid_accounts[0]
    settings = {
        "base_url": IFLOW_API_BASE,
        "access_token": primary["token"],
        "account_id": primary["id"],
        "email": primary.get("email", ""),
    }
    settings_file = data_dir / "settings.json"
    with open(settings_file, "w") as f:
        json.dump(settings, f, indent=2)
    print(f"  Wrote primary settings → {settings_file}")

    # Write per-account oauth_creds for multi-account rotation
    for a in valid_accounts:
        creds = {
            "access_token": a["token"],
            "refresh_token": "",
            "account_id": a["id"],
            "email": a.get("email", ""),
        }
        creds_file = data_dir / f"oauth_creds_{a['id']}.json"
        with open(creds_file, "w") as f:
            json.dump(creds, f, indent=2)
        print(f"  Wrote {creds_file}")

    print(f"\n✅ Synced {len(valid_accounts)} account(s) to {data_dir}")
    print("\nRestart iflow2api to pick up changes:")
    print("  docker-compose restart iflow2api")


def cmd_export_env(args):
    """Print env-var additions for the gateway and docker-compose."""
    accounts = load_accounts()
    valid_accounts = [a for a in accounts if a.get("valid", True)]

    if not valid_accounts:
        print("No valid accounts. Run: python scripts/iflow_login.py add")
        return

    print("\n# ── Add to .env (for iflow2api service) ──")
    print("IFLOW2API_BASE_URL=http://iflow2api:3000")
    print("IFLOW2API_KEY=sk-iflow-internal-key")
    print()
    print("# ── Add to iflow2api/.env ──")
    for i, a in enumerate(valid_accounts):
        key = "IFLOW_TOKEN" if i == 0 else f"IFLOW_TOKEN_{i+1}"
        print(f"{key}={a['token']}")

    print()
    print("# ── docker-compose.yml service block ──")
    print("""
  iflow2api:
    build:
      context: ./iflow2api
    container_name: iflow2api
    ports:
      - "3010:3000"
    volumes:
      - ./iflow2api/data:/app/data
    environment:
      - API_KEY=sk-iflow-internal-key
    restart: always
    networks:
      - inference-net
""")


# ──────────────────────────────────────────────
# Entry point
# ──────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Manage iFlow OAuth tokens for the AI gateway",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    subparsers = parser.add_subparsers(dest="command")

    add_parser = subparsers.add_parser("add", help="Add a new iFlow account")
    add_parser.add_argument("--cli", action="store_true", help="Use iflow-cli to authenticate")

    subparsers.add_parser("list", help="List all accounts")
    subparsers.add_parser("validate", help="Re-validate all tokens")

    rm = subparsers.add_parser("remove", help="Remove an account")
    rm.add_argument("account_id")

    subparsers.add_parser("sync-proxy", help="Write creds for iflow2api Docker service")
    subparsers.add_parser("export-env", help="Print .env additions")

    args = parser.parse_args()

    commands = {
        "add": cmd_add,
        "list": cmd_list,
        "validate": cmd_validate,
        "remove": cmd_remove,
        "sync-proxy": cmd_sync_proxy,
        "export-env": cmd_export_env,
    }

    if args.command in commands:
        commands[args.command](args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
