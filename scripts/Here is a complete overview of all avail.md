Here is a complete overview of all available models, their endpoints, how they are routed under the hood, and how the fallback system behaves.

Standard Request Endpoints
The gateway mimics standard OpenAI/Anthropic/Gemini APIs, meaning you can drop this into almost any AI GUI (like Cherry Studio, Cline, Open WebUI) by just switching the Base URL to your domain and dropping in your gateway API key:

OpenAI Format (Recommended for everything): POST https://aikompute.com/v1/chat/completions
Anthropic Format: POST https://aikompute.com/v1/messages
Gemini Format: POST https://aikompute.com/v1beta/models/{model}:generateContent
List Models: GET https://aikompute.com/v1/models
Available Models & Routing Definitions
When you send a request to the gateway, it intercepts the 

model
 parameter you requested and forwards it natively to the 

AIClient2API
 protocol transformers, utilizing rotating account pools based on the following map:

🟢 1. Antigravity Provider (Gemini & Claude 4.6 accounts)
Routed to: gemini-antigravity

gemini-2.0-flash
gemini-2.5-pro
gemini-2.5-flash
gemini-3.0-pro
gemini-3.0-flash
gemini-3.1-pro-high
gemini-3.1-pro-low
gemini-3.5-flash
gemini-pro, gemini-flash
gemini-2.5-computer-use-preview-10-2025
claude-sonnet-4-6
claude-opus-4-6
🔵 2. Amazon Kiro Provider (Claude 4.5/4.0 accounts)
Routed to: claude-kiro-oauth

claude-sonnet-4-5
kiro-claude-sonnet-4-5
claude-opus-4-5
kiro-claude-opus-4-5-thinking
claude-sonnet-4
claude-opus-4
claude-haiku-3-5
🟠 3. Qwen OAuth Provider (Qwen accounts)
Routed to: openai-qwen-oauth

qwen3-coder-plus
qwen3-coder
qwen-turbo
🟣 4. GitHub Copilot Proxy (via the copilot-api service)
Routed to: copilot-api (If you linked a GitHub account with a Copilot Free/Pro subscription)

copilot-gpt-4o (Native GPT-4o)
copilot-gpt-4.1 (Native GPT-4.1)
copilot-o4-mini
copilot-claude-sonnet (Native Claude 3.5 Sonnet)
copilot-claude-haiku
⚪ 5. GitHub Models API (via GitHub PAT token)
Routed to: github-models (Free tiers for these models)

github-gpt-4o
github-gpt-4.1
github-o4-mini
github-claude-sonnet
github-gemini-pro
github-deepseek-v3
🔴 6. Direct Paid APIs
Routed direct to providers

gpt-4o (Routes to openai-iflow)
deepseek-v3, deepseek-r1 (Routes to openai-iflow)
claude-3-5-sonnet (Routes to claude-custom)
How Auto-Routing & Fallbacks Work
If you pass a model name that maps to a specific provider (e.g., model="claude-sonnet-4-5"), the gateway will attempt to resolve it to its designated primary provider (claude-kiro-oauth).

If that provider is out of capacity, heavily rate-limited, or throwing 403s/500s, it kicks off a Fallback Chain.

Model "auto" routing: If you pass model="auto", it completely ignores specific mappings and just hunts down the list for the highest-ranking provider that has healthy accounts right now.
Tripped Circuit Breaker: If a provider fails multiple times in a row, the 

circuit_breaker.py
 marks it as open_circuit. All requests for that provider are instantly bypassed to prevent your users from waiting for timeouts.
The Fallback Queue: When a target provider fails or is bypassed, the system cascades down the AUTO_ROUTE_ORDER:
gemini-antigravity
gemini-cli-oauth
claude-kiro-oauth
openai-qwen-oauth
copilot-api
github-models
So, for example, if a user requests a Qwen model and openai-qwen-oauth has exhausted its tokens, it will attempt to fulfill the prompt via gemini-antigravity.

Wait, what if I don't want it returning a different model during a fallback? Right now, the default behavior aims solely for availability (answering the prompt by any means necessary so the API call doesn't crash on the user). However, AIClient2API handles intelligent protocol mapping, meaning even if a Claude endpoint fails and it falls back to Gemini, it will translate the Claude system context/tools on the fly so the user's GUI doesn't break.

