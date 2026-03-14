"""
windsurf_capture.py - mitmproxy addon script
Captures all traffic to/from Windsurf (Codeium) servers.

Usage:
  mitmdump -s windsurf_capture.py --ssl-insecure -p 8080

All captured requests/responses are written to:
  C:\\Users\\Administrator\\coding\\ai\\scripts\\windsurf_traffic.json
"""

import json
import time
import os
from datetime import datetime
from mitmproxy import http

# Codeium / Windsurf backend hostnames to capture
TARGET_HOSTS = {
    "server.codeium.com",
    "api.codeium.com",
    "windsurf.codeium.com",
    "codeiumdata.com",
    "codeium.com",
}

OUTPUT_FILE = os.path.join(
    os.path.dirname(__file__), "windsurf_traffic.json"
)

# In-memory log — flushed to disk after each response
captured = []


def _matches_target(host: str) -> bool:
    host = host.lower()
    return any(host == t or host.endswith("." + t) for t in TARGET_HOSTS)


def request(flow: http.HTTPFlow) -> None:
    """Called for every request. Log headers + body for Codeium hosts."""
    host = flow.request.host
    if not _matches_target(host):
        return

    entry = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "direction": "REQUEST",
        "method": flow.request.method,
        "url": flow.request.pretty_url,
        "host": host,
        "path": flow.request.path,
        "http_version": flow.request.http_version,
        "headers": dict(flow.request.headers),
        "body_raw": None,
        "body_json": None,
    }

    # Try to decode body
    try:
        raw = flow.request.content.decode("utf-8", errors="replace")
        entry["body_raw"] = raw
        entry["body_json"] = json.loads(raw)
    except Exception:
        pass

    # Tag the flow so we can match the response later
    flow.metadata["windsurf_entry_idx"] = len(captured)
    captured.append(entry)

    print(f"\n{'='*60}")
    print(f"[WINDSURF REQUEST] {entry['method']} {entry['url']}")
    print(f"  Auth header : {entry['headers'].get('authorization', entry['headers'].get('Authorization', 'NONE'))}")
    if entry["body_json"]:
        print(f"  Body (JSON) : {json.dumps(entry['body_json'], indent=2)[:1000]}")
    elif entry["body_raw"]:
        print(f"  Body (raw)  : {entry['body_raw'][:500]}")

    _flush()


def response(flow: http.HTTPFlow) -> None:
    """Called after each response arrives."""
    host = flow.request.host
    if not _matches_target(host):
        return

    resp_entry = {
        "status_code": flow.response.status_code,
        "headers": dict(flow.response.headers),
        "body_raw": None,
        "body_json": None,
    }

    try:
        raw = flow.response.content.decode("utf-8", errors="replace")
        resp_entry["body_raw"] = raw[:8000]  # cap at 8KB
        resp_entry["body_json"] = json.loads(raw)
    except Exception:
        pass

    # Attach response to the matching request entry
    idx = flow.metadata.get("windsurf_entry_idx")
    if idx is not None and idx < len(captured):
        captured[idx]["response"] = resp_entry
    else:
        # Orphan response (e.g. from a cached request)
        captured.append({
            "direction": "ORPHAN_RESPONSE",
            "url": flow.request.pretty_url,
            **resp_entry,
        })

    print(f"\n[WINDSURF RESPONSE] {flow.response.status_code} ← {flow.request.pretty_url}")
    if resp_entry["body_json"]:
        print(f"  Body (JSON) : {json.dumps(resp_entry['body_json'], indent=2)[:1000]}")
    elif resp_entry["body_raw"]:
        print(f"  Body (raw)  : {resp_entry['body_raw'][:500]}")

    _flush()


def _flush():
    """Write current capture log to disk."""
    try:
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            json.dump(captured, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"[ERROR] Failed to write traffic log: {e}")
