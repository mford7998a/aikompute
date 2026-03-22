# AI Inference Gateway - Agent Log

## Project Summary
**AI Inference Gateway** is a self-hosted, scalable proxy layer that provides a unified, OpenAI-compatible API to access over 12 different AI models (including GPT-4o, Claude 3.5 Sonnet, Gemini 2.0, DeepSeek, etc.) across various upstream providers (Antigravity, Amazon Kiro, Gemini CLI, GitHub Copilot Proxy, etc.).

The system consists of:
1. **Gateway (`gateway/`)**: A FastAPI backend that handles user authentication (JWT/API keys), rate limiting, pricing metrics, and token-based billing database logging.
2. **AIClient2API (`aiclient2api`)**: A Node.js service that handles protocol transformation, translating incoming requests into the respective upstream provider's protocol, managing account pools and fallback chains.
3. **Dashboard (`dashboard/`)**: A web interface for users to sign up, manage their API keys, check balances, and view their usage analytics.
4. **Nginx (`nginx/`)**: A reverse proxy that handles SSL termination, WebSockets, and routes incoming traffic to the appropriate service.
5. **PostgreSQL / Redis**: Databases for persistent storage (users, transactions, logs) and real-time state management (rate limiting, health scores).

---

## 🤖 Instructions for Future Agents
1. **Log Every Change**: Whenever you modify the codebase, system configuration, or infrastructure, you MUST append an entry to this file.
2. **Format**: Use the format below for consistency. Include the date, the agent (or "User"), and a brief description of the files modified and the reason for the change.
3. **Check Context**: Read this log to understand recent changes and debug historical issues.

---

## Change Log

### [2026-03-22] Agent Actions
* **Landing Page Migration (`dashboard/index.html`, `dashboard/auth.html`, `dashboard/landing.css`, `dashboard/landing.js`, `nginx/app.conf`)**:
  * Moved the "new landing page" into the primary `aikompute.com/` root by replacing `dashboard/index.html` with the contents of `landing/index.html`.
  * Preserved the original dashboard functionality by renaming the old `dashboard/index.html` to `dashboard/auth.html`.
  * Added specific Nginx proxy routes for `/login` and `/signup` that serve `auth.html` directly.
  * Implemented route-awareness in `auth.html` (via a new `<script>` block) to automatically display the registration form when the visitor arrives via the `/signup` path.
  * Renamed landing page assets to `landing.css` and `landing.js` within the `dashboard/` folder to prevent naming collisions with the dashboard's `styles.css` and `app.js`.
  * Updated all hardcoded `https://aikompute.com/login` and `/signup` links in the landing page to use relative paths for better portability.

* **Landing Page Content Update (`dashboard/index.html`, `dashboard/landing.css`)**:
  * Updated hero section to prioritize Claude Sonnet/Opus and Gemini 3.1 branding.
  * Added stylized model chips for quick recognition of available frontier models.
  * Updated the Model Catalog table with the latest high-performance coding models (GPT 5.1 Codex, Claude 4.6, Gemini 3.1).


### [2026-03-22] Agent Actions (Continued)
* **Native Protocol Endpoints (`gateway/routes_native.py`, `gateway/main.py`, `nginx/app.conf`)**:
  * Added Native Anthropic Endpoint (`POST /v1/messages`) allowing tools like Roo Code to bypass OpenAI conversion entirely and send native JSON tool schemas directly to the upstream proxy.
  * Added Native Gemini Endpoints (`POST /v1beta/models/{model}:generateContent` and `streamGenerateContent`).
  * Implemented SSE stream parsing tailored to the specific chunk formats of Anthropic (`content_block_delta`) and Gemini to ensure output text tokens are properly aggregated, metered, and accurately billed to the user's PostgreSQL database balance.
  * **Fixed streaming**: Rewrote the SSE proxy to use raw `aiter_bytes()` passthrough instead of `aiter_lines()`. The old approach stripped blank-line separators between SSE events, corrupting the `event:`/`data:` format that Roo Code requires. Now raw bytes flow through untouched while billing sniffs content in parallel.
  * **User Documentation (`docs/guide_agent_setup.md`, `docs/api_reference.md`)**:
    * Created a dedicated guide for setting up **Roo Code**, **Cline**, and **Cursor** using the new native protocol endpoints.
    * Updated the API reference to include clear instructions and `curl` examples for **Native Anthropic** (`POST /v1/messages`) and **Native Gemini** (`POST /v1beta/`).
    * Documented how to choose between standard OpenAI compatibility and high-reliability native protocols for specific agent use cases.

* **Routing & Model Translation Fixes (`gateway/proxy.py`)**:
  * Removed all internal model substitutions for Antigravity, Gemini CLI, and Kiro. The gateway now passes the exact requested model name (e.g. `claude-sonnet-4-6`) directly to the upstream provider since they handle model mappings natively.
  * Updated `chat_completion_stream()` to actually use the translated model name (was previously sending raw frontend aliases which crashed upstream providers).
  * Promoted `gemini-antigravity` to be the primary provider for all Claude models, with `claude-kiro-oauth` acting as the fallback.
* **Streaming Stability (`gateway/routes_chat.py`)**:
  * Fixed an ASGI worker crash (502 Gateway Error) by replacing bare `HTTPException` raises with yielded JSON-formatted error chunks.
  * Corrected severe Python syntax errors in the fallback loop (an orphaned `finally` block).
* **Admin & Dashboard Configuration**:
  * Verified Nginx properly routes `antigravity.aikompute.com` to `antigravity2api` on port `8045`.
  * Synced hardcoded `API_KEY` strings between `antigravity2api-nodejs/.env` and the root `.env` file so Docker composition matches the server state.

### [2026-03-19] Agent Actions
* **OpenRouter Provider Integration (`gateway/proxy.py`, `gateway/routes_chat.py`, `gateway/config.py`, `docker-compose.prod.yml`)**:
  * Added OpenRouter as a new provider with 19 free-tier models (Llama 3.3 70B, Gemma 3 27B, Hermes 3 405B, Mistral Small 3.1, Nemotron 3 Super 120B, etc.)
  * Implemented round-robin API key rotation via `itertools.cycle` for account pooling across multiple OpenRouter accounts (configured via comma-separated `OPENROUTER_API_KEYS` env var)
  * All models prefixed with `or-` (e.g., `or-llama-3.3-70b`) which translate to full OpenRouter model IDs (e.g., `meta-llama/llama-3.3-70b-instruct:free`)
  * Added OpenRouter-specific headers (`HTTP-Referer`, `X-Title`) required by their API
  * Added `OPENROUTER_API_KEYS` and `OPENROUTER_BASE_URL` to config.py and docker-compose.prod.yml

### [2026-03-18] Agent Actions
* **Same-Model-Only Fallback Logic (`gateway/proxy.py`, `gateway/routes_chat.py`)**:
  * Added `MODEL_PROVIDERS` mapping that lists ALL providers capable of serving each specific model.
  * Added `resolve_fallback_providers()` function that returns only same-model providers for fallback.
  * Changed `routes_chat.py` to use `resolve_fallback_providers()` instead of the old logic that appended every provider from `AUTO_ROUTE_ORDER` as a fallback (which would substitute different models).
  * Updated `try_with_fallback()` to return a clear 503 error with message: "The requested model '{model}' is currently experiencing high usage and all providers are temporarily unavailable. Please try again in 30 to 60 seconds." when all same-model providers are exhausted.

### [2026-03-16] Agent Actions
* **Nginx Configuration (`nginx/app.conf`)**: 
  * Initially attempted to use `sub_filter` to route the AIClient2API admin panel out of a subpath (`/admin/`).
  * Eventually separated the admin panel into its own subdomain (`admin.aikompute.com`) to avoid API path collisions (`/api/...`) with the FastAPI Gateway, allowing direct transparent routing.
  * Added proper WebSocket proxy headers (`Upgrade $http_upgrade`, `Connection "upgrade"`) to fix the "DISCONNECTED" state in the admin panel.
* **Dashboard Frontend (`dashboard/app.js`)**: 
  * Fixed a bug where `API_BASE` was hardcoded to `http://localhost:4000` or `:4000`, causing timeouts (`net::ERR_CONNECTION_TIMED_OUT`) when accessing via Cloudflare. Update it to use `window.location.host`.
* **Database Initialization (`migrations/01_init.sql`)**: 
  * Created the initial database schema (tables: `users`, `api_keys`, `credit_transactions`, `usage_logs`, `credit_packages`, `model_pricing`) because the FastAPI gateway was throwing an `UndefinedTableError` for the `users` table on user registration.
* **Testing Scripts (`scripts/test_models.py`)**: 
  * Updated `GATEWAY_URL` to point to production (`https://aikompute.com/v1/chat/completions`).
  * Updated the hardcoded API key.
  * Added `User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36` to headers to bypass Cloudflare's **Error 1010 (403 Forbidden)** block against generic `urllib` requests.

### [2026-03-15] Agent Actions
* **Deployment Script (`vm_setup.sh`)**: 
  * Consolidated setup scripts. Generates random secrets (`DB_PASS`, `REDIS_PASS`, `JWT_SECRET`, etc.) and automatically drops them into a `.env` file and `aiclient2api-configs/config.json`.
  * Configures Nginx with the user's provided domain name and uses Certbot to provision a Let's Encrypt SSL certificate.
