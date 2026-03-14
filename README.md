# AI Inference Gateway

**A commercial-grade AI inference proxy that provides users with OpenAI-compatible API access, charges per-token, and fulfills requests by routing through free-tier IDE-based AI tools (Google Antigravity, Amazon Kiro, Gemini CLI, Qwen Code) and paid API providers.**

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  Users (any OpenAI SDK / curl / application)                │
│  Authorization: Bearer sk-inf-xxxxxxx                       │
└─────────────────┬───────────────────────────────────────────┘
                  │
                  ▼ Port 4000
┌─────────────────────────────────────────────────────────────┐
│  Billing Gateway (FastAPI)                                  │
│  ┌──────────┐ ┌──────────┐ ┌───────────┐ ┌──────────────┐  │
│  │ Auth     │ │ Rate     │ │ Token     │ │ Credit       │  │
│  │ (API key)│ │ Limiter  │ │ Meter     │ │ Billing      │  │
│  └──────────┘ └──────────┘ └───────────┘ └──────────────┘  │
└─────────────────┬───────────────────────────────────────────┘
                  │
                  ▼ Port 3001 (internal)
┌─────────────────────────────────────────────────────────────┐
│  AIClient-2-API (Node.js) — github.com/justlovemaki        │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ Protocol Transformation Engine                       │   │
│  │ • Gemini CLI OAuth → OpenAI format                   │   │
│  │ • Antigravity OAuth → OpenAI format                  │   │
│  │ • Kiro OAuth → OpenAI format (Claude models)         │   │
│  │ • Qwen Code OAuth → OpenAI format                    │   │
│  │ • Native OpenAI/Claude passthrough                   │   │
│  └──────────────────────────────────────────────────────┘   │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ Account Pool Manager (built-in)                      │   │
│  │ • LRU scoring — uses least-recently-used account     │   │
│  │ • Priority tiers — primary accounts first, backups   │   │
│  │ • Health checks — auto-disable unhealthy accounts    │   │
│  │ • Error recovery — re-enable after cooldown          │   │
│  │ • Fallback chains — Gemini CLI → Antigravity → Paid  │   │
│  └──────────────────────────────────────────────────────┘   │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ OAuth Manager                                        │   │
│  │ • Auto token refresh before expiry                   │   │
│  │ • Web UI for visual credential management            │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────┬───────────────────────────────────────────┘
                  │
                  ▼
┌──────────┐ ┌─────────────┐ ┌──────┐ ┌──────┐ ┌───────────┐
│ Gemini   │ │ Antigravity │ │ Kiro │ │ Qwen │ │ OpenAI /  │
│ CLI      │ │ (Google)    │ │(AWS) │ │ Code │ │ Claude    │
│ (Free)   │ │ (Free)      │ │(Free)│ │(Free)│ │ (Paid)    │
└──────────┘ └─────────────┘ └──────┘ └──────┘ └───────────┘
```

## How Account Rotation Works

1. **You add multiple accounts** per provider in `aiclient2api-configs/provider_pools.json`
2. **AIClient-2-API rotates between them** using LRU (least-recently-used) scoring
3. **When an account hits rate limits** (429 error), it's temporarily marked unhealthy
4. **The next request uses a different account** from the same pool
5. **If ALL accounts in a pool are exhausted**, the fallback chain kicks in:
   - `gemini-cli-oauth` → `gemini-antigravity` → `openai-custom`
   - `claude-kiro-oauth` → `claude-custom`
6. **Health checks run periodically** to restore recovered accounts

## How Protocol Transformation Works

AIClient-2-API simulates the actual IDE client requests:

| User Sends (OpenAI format) | AIClient-2-API Transforms To | Provider |
|---|---|---|
| `POST /gemini-cli-oauth/v1/chat/completions` | Gemini CLI OAuth protocol | Google Gemini |
| `POST /gemini-antigravity/v1/chat/completions` | Antigravity internal protocol | Google Antigravity |
| `POST /claude-kiro-oauth/v1/chat/completions` | Kiro client protocol | Amazon Kiro (Claude) |
| `POST /openai-qwen-oauth/v1/chat/completions` | Qwen Code OAuth protocol | Alibaba Qwen |

The user never needs to know about these transformations — they just use standard OpenAI API format.

## Quick Start

### 1. Clone and configure

```bash
git clone <this-repo>
cd ai-inference-gateway

# Copy environment template
cp .env.example .env
# Edit .env with your settings
```

### 2. Add provider credentials

Open `http://localhost:3001` (AIClient-2-API Web UI) after starting, or manually:

```bash
# Gemini CLI — run in your browser to get OAuth credentials
# The credentials file gets saved to ~/.gemini/oauth_creds.json
# Copy it to:
cp ~/.gemini/oauth_creds.json aiclient2api-configs/gemini/oauth_creds_1.json

# Kiro — install Kiro IDE, login, then copy the auth token
cp ~/.aws/sso/cache/kiro-auth-token.json aiclient2api-configs/kiro/kiro_auth_1.json

# Antigravity — requires Antigravity IDE login
cp ~/.antigravity/oauth_creds.json aiclient2api-configs/antigravity/oauth_creds_1.json
```

### 3. Start all services

```bash
docker compose up -d
```

### 4. Create a user account

```bash
curl http://localhost:4000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "password": "mypassword"}'
```

Save the `api_key` from the response.

### 5. Make API calls

```bash
# Using curl
curl http://localhost:4000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer sk-inf-YOUR-KEY" \
  -d '{
    "model": "gemini-3.0-pro",
    "messages": [{"role": "user", "content": "Hello!"}]
  }'

# Using Python OpenAI SDK
from openai import OpenAI
client = OpenAI(api_key="sk-inf-YOUR-KEY", base_url="http://localhost:4000/v1")
response = client.chat.completions.create(
    model="claude-sonnet-4-5",
    messages=[{"role": "user", "content": "Explain quantum computing"}]
)
```

## Services

| Service | Port | Description |
|---------|------|-------------|
| **Billing Gateway** | 4000 | Your user-facing API (auth, billing, rate limiting) |
| **Dashboard** | 3000 | User dashboard (manage keys, view usage, buy credits) |
| **AIClient-2-API** | 3001 | Protocol transformation + account rotation (internal) |
| **PostgreSQL** | 5432 | User data, usage logs, billing |
| **Redis** | 6379 | Rate limiting, caching |

## Available Models

| Model | Routed Via | Cost Tier |
|-------|-----------|-----------|
| `gemini-2.0-flash` | Gemini CLI (free) | 💚 Lowest |
| `gemini-2.5-pro` | Gemini CLI (free) | 💚 Lowest |
| `gemini-3.0-pro` | Antigravity (free) | 💚 Lowest |
| `claude-sonnet-4-5` | Kiro (free) | 💛 Low |
| `claude-opus-4-5` | Kiro (free) | 💛 Low |
| `qwen3-coder-plus` | Qwen Code (free) | 💚 Lowest |
| `gpt-4o` | OpenAI API (paid) | 🔴 High |
| `auto` | Best available | 💚 Auto-optimized |

## Project Structure

```
ai-inference-gateway/
├── docker-compose.yml              # Orchestrates all services
├── .env.example                    # Environment variables template
├── gateway/                        # FastAPI billing gateway
│   ├── main.py                     # App entry point
│   ├── config.py                   # Settings
│   ├── auth.py                     # API key + JWT auth
│   ├── billing.py                  # Token counting + credit billing
│   ├── proxy.py                    # Forwards requests to AIClient-2-API
│   ├── rate_limiter.py             # Redis-based rate limiting
│   ├── routes_chat.py              # /v1/chat/completions endpoint
│   ├── routes_users.py             # User management, billing, usage
│   └── database.py                 # PostgreSQL connection
├── aiclient2api-configs/           # AIClient-2-API configuration
│   ├── config.json                 # Main config (fallback chains, etc.)
│   ├── provider_pools.json         # Account pools for rotation
│   ├── gemini/                     # Gemini OAuth credential files
│   ├── antigravity/                # Antigravity OAuth credential files
│   ├── kiro/                       # Kiro auth token files
│   └── qwen/                       # Qwen OAuth credential files
├── dashboard/                      # User-facing web dashboard
│   ├── index.html
│   ├── styles.css
│   └── app.js
└── migrations/                     # PostgreSQL schema
    └── 001_schema.sql
```

## Pricing Management

The gateway uses a precise **Micro-Credit** system for billing:
- **1 Credit = 1,000,000 Micro-credits**
- Prices are defined as **USD per 1 Million Tokens**.
- Example: If you set a model price to `$1.00`, the system will charge `1,000,000` micro-credits for 1 million tokens.

### Using the Pricing Utility

We provide a specialized tool in `scripts/manage_pricing.py` to manage your margins without touching raw SQL.

#### 1. Setup
```bash
# Install dependencies
pip install psycopg2-binary python-dotenv
```

#### 2. List current rates
```bash
python scripts/manage_pricing.py list
```

#### 3. Update or Add a Rate
```bash
# Usage: python manage_pricing.py set <pattern> <provider|any> <in_usd_per_1M> <out_usd_per_1M> [priority]

# Set GPT-4o pricing to $5/1M input and $15/1M output
python scripts/manage_pricing.py set "gpt-4o" "openai-custom" 5.0 15.0 20

# Set a high margin for all Antigravity models ($0.50/$1.00)
python scripts/manage_pricing.py set "*" "gemini-antigravity" 0.5 1.0 10

# Set a catch-all default for any unknown model ($1.00/$2.00)
python scripts/manage_pricing.py set "*" "any" 1.0 2.0 0
```

> [!TIP]
> **Priority Matters**: If multiple patterns match a request, the one with the **highest priority** is used. Use high priority (e.g., 20) for specific models and low priority (e.g., 0) for catch-all patterns.

## Alternative: Using new-api Instead of Custom Gateway

If you prefer a pre-built billing layer, you can replace our FastAPI gateway with
[new-api](https://github.com/Calcium-Ion/new-api) (a Go-based LLM management/billing system):

1. Deploy new-api instead of the `gateway` service
2. Add AIClient-2-API endpoints as "channels" in new-api:
   - Channel: `http://aiclient2api:3000/gemini-cli-oauth/v1` (type: OpenAI)
   - Channel: `http://aiclient2api:3000/claude-kiro-oauth/v1` (type: OpenAI)
   - etc.
3. new-api handles users, API keys, quotas, and Stripe billing

Trade-off: new-api is battle-tested with a large community, but our custom gateway
gives you per-model/per-provider differential pricing and tighter control.

## License

MIT
