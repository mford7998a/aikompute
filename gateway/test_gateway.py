"""
Test suite for the AI Inference Gateway.
Tests module imports, token counting, cost calculation, API key generation,
auth flows, and API endpoint responses.
"""
import sys
import os
import json
import asyncio
import hashlib

# Ensure gateway modules are importable
sys.path.insert(0, os.path.dirname(__file__))

PASS = 0
FAIL = 0

def test(name, condition, detail=""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  ✅ {name}")
    else:
        FAIL += 1
        print(f"  ❌ {name} — {detail}")


print("\n" + "="*60)
print("  AI Inference Gateway — Test Suite")
print("="*60)


# ============================================
# Test 1: Module imports
# ============================================
print("\n📦 Module Imports:")

try:
    from config import settings
    test("config.py imports", True)
except Exception as e:
    test("config.py imports", False, str(e))

try:
    import auth
    test("auth.py imports", True)
except Exception as e:
    test("auth.py imports", False, str(e))

try:
    import billing
    test("billing.py imports", True)
except Exception as e:
    test("billing.py imports", False, str(e))

try:
    import proxy
    test("proxy.py imports", True)
except Exception as e:
    test("proxy.py imports", False, str(e))

try:
    import rate_limiter
    test("rate_limiter.py imports", True)
except Exception as e:
    test("rate_limiter.py imports", False, str(e))

try:
    import routes_chat
    test("routes_chat.py imports", True)
except Exception as e:
    test("routes_chat.py imports", False, str(e))

try:
    import routes_users
    test("routes_users.py imports", True)
except Exception as e:
    test("routes_users.py imports", False, str(e))

try:
    import routes_admin
    test("routes_admin.py imports", True)
except Exception as e:
    test("routes_admin.py imports", False, str(e))

try:
    import main
    test("main.py imports (full app)", True)
except Exception as e:
    test("main.py imports (full app)", False, str(e))


# ============================================
# Test 2: Token counting
# ============================================
print("\n🔢 Token Counting:")

from billing import count_tokens, count_message_tokens, calculate_cost

tokens = count_tokens("Hello, world!")
test("count_tokens basic", tokens > 0, f"got {tokens}")
test("count_tokens value", 2 <= tokens <= 5, f"expected 2-5, got {tokens}")

tokens_empty = count_tokens("")
test("count_tokens empty string", tokens_empty == 0)

tokens_long = count_tokens("The quick brown fox jumps over the lazy dog. " * 100)
test("count_tokens long text", tokens_long > 100, f"got {tokens_long}")

messages = [
    {"role": "system", "content": "You are a helpful assistant."},
    {"role": "user", "content": "What is the meaning of life?"},
]
msg_tokens = count_message_tokens(messages)
test("count_message_tokens", msg_tokens > 10, f"got {msg_tokens}")
test("message tokens include overhead", msg_tokens > count_tokens("You are a helpful assistant.What is the meaning of life?"))

# Multimodal message
multi_messages = [
    {"role": "user", "content": [
        {"type": "text", "text": "What's in this image?"},
        {"type": "image_url", "image_url": {"url": "https://example.com/img.png"}}
    ]}
]
multi_tokens = count_message_tokens(multi_messages)
test("multimodal message tokens", multi_tokens > 85, f"got {multi_tokens} (should include image estimate)")


# ============================================
# Test 3: Cost calculation
# ============================================
print("\n💰 Cost Calculation:")

pricing = {"input_cost_per_million": 200000, "output_cost_per_million": 400000}
cost = calculate_cost(1000, 500, pricing)
test("calculate_cost basic", cost > 0, f"got {cost}")

# 1M input tokens at 200000 micro-credits/M = 200000
cost_1m = calculate_cost(1_000_000, 0, pricing)
test("1M input tokens cost", cost_1m == 200000, f"expected 200000, got {cost_1m}")

# 1M output tokens at 400000 micro-credits/M = 400000
cost_1m_out = calculate_cost(0, 1_000_000, pricing)
test("1M output tokens cost", cost_1m_out == 400000, f"expected 400000, got {cost_1m_out}")

# Minimum cost is 1
cost_min = calculate_cost(1, 0, pricing)
test("minimum cost is 1", cost_min >= 1, f"got {cost_min}")

# Combined
cost_both = calculate_cost(500000, 500000, pricing)
expected = (500000 * 200000 // 1_000_000) + (500000 * 400000 // 1_000_000)
test("combined input+output cost", cost_both == expected, f"expected {expected}, got {cost_both}")


# ============================================
# Test 4: API key generation
# ============================================
print("\n🔑 API Key Generation:")

from auth import generate_api_key, hash_password, verify_password

full_key, key_hash, key_prefix = generate_api_key()
test("key starts with sk-inf-", full_key.startswith("sk-inf-"))
test("key length > 20", len(full_key) > 20, f"length={len(full_key)}")
test("key_hash is SHA-256", len(key_hash) == 64)
test("key_prefix is 12 chars", len(key_prefix) == 12)
test("hash matches key", key_hash == hashlib.sha256(full_key.encode()).hexdigest())

# Generate another key — should be unique
full_key2, key_hash2, _ = generate_api_key()
test("keys are unique", full_key != full_key2)
test("hashes are unique", key_hash != key_hash2)


# ============================================
# Test 5: Password hashing
# ============================================
print("\n🔒 Password Hashing:")

hashed = hash_password("mypassword123")
test("hash is not plaintext", hashed != "mypassword123")
test("hash starts with $2b$", hashed.startswith("$2b$"))
test("verify correct password", verify_password("mypassword123", hashed))
test("reject wrong password", not verify_password("wrongpassword", hashed))


# ============================================
# Test 6: JWT tokens
# ============================================
print("\n🎫 JWT Tokens:")

from auth import create_jwt, decode_jwt

token = create_jwt("user-123", "test@example.com", is_admin=False)
test("JWT is a string", isinstance(token, str))
test("JWT has 3 parts", len(token.split(".")) == 3)

decoded = decode_jwt(token)
test("JWT decodes user_id", decoded["sub"] == "user-123")
test("JWT decodes email", decoded["email"] == "test@example.com")
test("JWT decodes admin flag", decoded["admin"] == False)

admin_token = create_jwt("admin-1", "admin@test.com", is_admin=True)
admin_decoded = decode_jwt(admin_token)
test("admin JWT has admin=true", admin_decoded["admin"] == True)

# Invalid token should raise
try:
    decode_jwt("invalid.token.here")
    test("invalid JWT raises error", False, "should have raised")
except Exception:
    test("invalid JWT raises error", True)


# ============================================
# Test 7: Provider routing
# ============================================
print("\n🔀 Provider Routing:")

from proxy import resolve_provider, MODEL_TO_PROVIDER

test("gemini-3.0-pro → antigravity", resolve_provider("gemini-3.0-pro") == "gemini-antigravity")
test("gemini-2.5-pro → gemini-cli", resolve_provider("gemini-2.5-pro") == "gemini-cli-oauth")
test("claude-sonnet-4-5 → kiro", resolve_provider("claude-sonnet-4-5") == "claude-kiro-oauth")
test("gpt-4 → openai", resolve_provider("gpt-4") == "openai-custom")
test("qwen3-coder-plus → qwen", resolve_provider("qwen3-coder-plus") == "openai-qwen-oauth")

# Prefix-based inference for unknown models
test("gemini-future → gemini", resolve_provider("gemini-future-model").startswith("gemini"))
test("claude-future → kiro", resolve_provider("claude-future-model") == "claude-kiro-oauth")
test("gpt-5 → openai", resolve_provider("gpt-5") == "openai-custom")
test("qwen-turbo → qwen", resolve_provider("qwen-turbo") == "openai-qwen-oauth")
test("unknown → default", resolve_provider("unknown-model") == "gemini-cli-oauth")


# ============================================
# Test 8: Proxy URL building
# ============================================
print("\n🌐 Proxy URL Building:")

from proxy import proxy as proxy_instance

url = proxy_instance._build_url("gemini-cli-oauth")
test("gemini URL correct", url.endswith("/gemini-cli-oauth/v1/chat/completions"))

url2 = proxy_instance._build_url("claude-kiro-oauth")
test("kiro URL correct", url2.endswith("/claude-kiro-oauth/v1/chat/completions"))

headers = proxy_instance._build_headers()
test("headers have auth", "Authorization" in headers)
test("headers have content-type", headers["Content-Type"] == "application/json")


# ============================================
# Test 9: FastAPI app configuration
# ============================================
print("\n🚀 FastAPI App:")

from main import app

test("app title set", app.title == "AI Inference Gateway")
test("app version set", app.version == "1.0.0")

# Check routes exist
routes = [r.path for r in app.routes]
test("/v1/chat/completions registered", "/v1/chat/completions" in routes)
test("/v1/models registered", "/v1/models" in routes)
test("/health registered", "/health" in routes)
test("/api/auth/register registered", "/api/auth/register" in routes)
test("/api/auth/login registered", "/api/auth/login" in routes)
test("/api/user/keys registered", "/api/user/keys" in routes)
test("/api/user/usage registered", "/api/user/usage" in routes)
test("/api/user/balance registered", "/api/user/balance" in routes)
test("/api/billing/packages registered", "/api/billing/packages" in routes)
test("/api/pricing registered", "/api/pricing" in routes)
test("/api/admin/dashboard registered", "/api/admin/dashboard" in routes)
test("/api/admin/trends registered", "/api/admin/trends" in routes)
test("/api/admin/forecast registered", "/api/admin/forecast" in routes)
test("/api/admin/users registered", "/api/admin/users" in routes)
test("/api/admin/providers registered", "/api/admin/providers" in routes)


# ============================================
# Test 10: Config settings
# ============================================
print("\n⚙️  Config Settings:")

from config import settings

test("DB URL set", "postgresql" in settings.DATABASE_URL)
test("Redis URL set", "redis" in settings.REDIS_URL)
test("default RPM is 60", settings.DEFAULT_RPM == 60)
test("default TPM is 100000", settings.DEFAULT_TPM == 100000)
test("free credits > 0", settings.NEW_USER_FREE_CREDITS > 0)
test("provider priority is a list", isinstance(settings.PROVIDER_PRIORITY, list))
test("provider priority has entries", len(settings.PROVIDER_PRIORITY) >= 4)


# ============================================
# Summary
# ============================================
print("\n" + "="*60)
total = PASS + FAIL
if FAIL == 0:
    print(f"  🎉 ALL {total} TESTS PASSED!")
else:
    print(f"  ⚠️  {PASS}/{total} passed, {FAIL} failed")
print("="*60 + "\n")

sys.exit(FAIL)
