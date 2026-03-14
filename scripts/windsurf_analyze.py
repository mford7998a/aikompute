"""
windsurf_analyze.py
Reads windsurf_traffic.json and extracts:
  - Auth token format
  - API endpoints used
  - Request/response schemas
  - Models available

Run AFTER a capture session:
  python scripts/windsurf_analyze.py
"""

import json
import os
import sys
from collections import defaultdict

TRAFFIC_FILE = os.path.join(os.path.dirname(__file__), "windsurf_traffic.json")


def load_traffic():
    if not os.path.exists(TRAFFIC_FILE):
        print(f"ERROR: {TRAFFIC_FILE} not found. Run windsurf_mitm_setup.ps1 first.")
        sys.exit(1)
    with open(TRAFFIC_FILE, encoding="utf-8") as f:
        return json.load(f)


def summarize(entries):
    print(f"\n{'='*60}")
    print(f" Windsurf Traffic Analysis")
    print(f" Total entries captured: {len(entries)}")
    print(f"{'='*60}\n")

    endpoints = defaultdict(list)
    auth_tokens = set()
    api_keys = set()
    models_seen = set()

    for e in entries:
        if e.get("direction") != "REQUEST":
            continue

        url = e.get("url", "")
        method = e.get("method", "")
        host = e.get("host", "")
        headers = e.get("headers", {})
        body = e.get("body_json") or {}
        resp = e.get("response", {})
        resp_body = resp.get("body_json") or {}

        # --- Auth token extraction ---
        auth = headers.get("authorization") or headers.get("Authorization") or ""
        if auth and auth not in auth_tokens:
            auth_tokens.add(auth)

        # Check for api_key in body or query params
        for key in ["api_key", "apiKey", "api-key", "token", "access_token"]:
            val = body.get(key) or headers.get(key)
            if val:
                api_keys.add(f"{key}: {val}")

        # --- Endpoint grouping ---
        path = e.get("path", "").split("?")[0]
        endpoints[f"{method} {host}{path}"].append({
            "request_body_keys": list(body.keys()) if isinstance(body, dict) else [],
            "response_status": resp.get("status_code"),
            "response_body_keys": list(resp_body.keys()) if isinstance(resp_body, dict) else [],
        })

        # --- Model detection ---
        for field in ["model", "model_name", "modelName"]:
            m = body.get(field) or resp_body.get(field)
            if m:
                models_seen.add(str(m))

        # Check nested
        metadata = body.get("metadata") or {}
        if isinstance(metadata, dict):
            m = metadata.get("model") or metadata.get("model_name")
            if m:
                models_seen.add(str(m))

    # --- REPORT ---

    print("[ AUTH TOKENS FOUND ]")
    if auth_tokens:
        for t in auth_tokens:
            # Mask middle of token for display
            if len(t) > 30:
                display = t[:20] + "..." + t[-10:]
            else:
                display = t
            print(f"  {display}")
    else:
        print("  (none found — may be in cookies or gRPC headers)")

    print("\n[ API KEYS / TOKENS IN BODY/HEADERS ]")
    if api_keys:
        for k in api_keys:
            print(f"  {k[:80]}")
    else:
        print("  (none found)")

    print("\n[ ENDPOINTS HIT ]")
    for endpoint, calls in sorted(endpoints.items()):
        req_keys = set()
        resp_keys = set()
        statuses = set()
        for c in calls:
            req_keys.update(c["request_body_keys"])
            resp_keys.update(c["response_body_keys"])
            if c["response_status"]:
                statuses.add(c["response_status"])
        print(f"\n  {endpoint}")
        print(f"    Calls        : {len(calls)}")
        print(f"    Status codes : {statuses}")
        print(f"    Req body keys: {sorted(req_keys)}")
        print(f"    Resp body keys:{sorted(resp_keys)}")

    print("\n[ MODELS SEEN ]")
    if models_seen:
        for m in sorted(models_seen):
            print(f"  {m}")
    else:
        print("  (none found in top-level body fields)")

    print("\n[ FULL REQUEST DETAILS ]")
    for i, e in enumerate(entries):
        if e.get("direction") != "REQUEST":
            continue
        print(f"\n--- Request #{i+1} ---")
        print(f"  {e.get('method')} {e.get('url')}")
        headers = e.get("headers", {})
        # Print important headers
        for h in ["authorization", "Authorization", "x-api-key", "cookie", "user-agent", "content-type"]:
            if h in headers:
                val = headers[h]
                if len(val) > 100:
                    val = val[:80] + "..."
                print(f"  {h}: {val}")
        if e.get("body_json"):
            print(f"  Body: {json.dumps(e['body_json'], indent=4)[:2000]}")
        elif e.get("body_raw"):
            print(f"  Body (raw): {e['body_raw'][:500]}")
        resp = e.get("response", {})
        if resp:
            print(f"  Response status: {resp.get('status_code')}")
            if resp.get("body_json"):
                print(f"  Response body: {json.dumps(resp['body_json'], indent=4)[:2000]}")


if __name__ == "__main__":
    entries = load_traffic()
    summarize(entries)
