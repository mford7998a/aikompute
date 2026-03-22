# AI Inference Gateway - Project Goals & Architecture

## 1. Core Vision & Business Objective
This project is designed to be a **commercial AI inference engine deployed in the cloud** and exposed to the public internet. 
The primary business model is to **provide API access to top-tier frontier models (Claude, Gemini, OpenAI)** at a price significantly lower than what official providers charge. 

**How this is achieved:**
By utilizing and routing requests through a fleet of free-tier IDE-based AI tools, student accounts, and trial subscriptions. The system masks these various specific service protocols behind a unified, standard **OpenAI-compatible API format**, parsing inputs and outputs symmetrically so end users (your customers) experience it just like using the official APIs.

## 2. Infrastructure & Cloud Deployment
This system is meant to be a **robust, multi-tenant, cloud-native application**:
- **Public Exposure**: Needs to run securely on a server facing the public internet.
- **Concurrency & Scaling**: Must handle high volumes of concurrent requests across thousands of users without cross-contamination of sessions.
- **Security & Multi-Tenancy**: Complete isolation of user data, strict API key validation, and defense against abuse/DDoS.

## 3. Core System Components

### A. The Billing Gateway (FastAPI)
The central nervous system of the commercial product. It sits in front of all proxy engines and handles:
- **Authentication**: Issuing and validating user API keys via JWT/Database.
- **Token Metering & Billing**: Counting tokens in real-time and debiting user balances using a Micro-Credit system (1 Credit = 1,000,000 Micro-credits).
- **Rate Limiting**: Utilizing Redis to enforce Requests Per Minute (RPM) and Tokens Per Minute (TPM).
- **Payment Processing**: Integrating with Stripe so customers can purchase credits.

### B. User Frontend Dashboard
A web portal deployed for end-users where they can:
- Create and manage their accounts.
- Generate and revoke API keys.
- Add payment methods and purchase inference credits.
- View real-time usage statistics and billing history.

### C. Protocol Transformation Layers (The Engines)
These microservices take standard OpenAI-formatted requests and translate them into proprietary protocols for various backends. They also handle account rotation, utilizing LRU (Least-Recently-Used) scoring to cycle through pools of free/trial credentials.
- **Antigravity2API**: Specialized proxy optimized for Antigravity, primarily used to supply **Google Gemini** models.
- **AIClient2API (incorporating Kiro)**: The primary engine translating OAuth protocols, critically utilizing Amazon Kiro to supply **Claude** models, as well as handling Qwen and Gemini CLI. 
- **Copilot-API**: Leverages GitHub Copilot authentication to act as an OpenAI/Anthropic proxy.


## 4. Key Goals for Future Development (Agent Directives)

Future AI agents working on this project must strictly adhere to these tenets:

1. **Commercial Stability**: Code changes must prioritize stability for a multi-tenant cloud environment. This is not a local hack tool; it is a public-facing commercial service. Do not introduce single-threaded bottlenecks or local-only dependencies.
2. **Account Rotation Resiliency**: The core to profitability is keeping the free/trial accounts alive. Agents must improve and maintain account pool managers, ensuring proper health checks, cool-down periods on 429s (Too Many Requests rate limits), and seamless fallback chains (e.g., if one source fails, fallback to the next).
3. **Symmetrical API Behavior**: End users expect a flawless OpenAI-compatible API. Ensure that streaming (`stream: true`), tool calling (`tool_choice`), and error formatting perfectly mimic OpenAI's standard behavior regardless of the underlying provider (Kiro, Antigravity, etc.).
4. **Billing Accuracy**: No free inference escapes. Ensure the Token Meter accurately calculates input/output tokens before returning responses and safely decrements the PostgreSQL database balances.
5. **Security First**: Assume the public API will be attacked. Validate all inputs, secure the PostgreSQL and Redis instances, and never expose master keys or backend credentials in client-side code or logs.

## 5. Model Availability & Fallback Routing

To maximize margins, the system routes models to specific free-tier backend providers. It relies heavily on an aggressive fallback architecture. If one account fails (e.g., hits a 429 rate limit or network error), the prompt is rerouted seamlessly to an alternative account/supplier before returning to the user.

### A. The Primary Providers
These are the sources configured via AIClient2API based on the current free-tier account pools (`aiclient2api-configs/provider_pools.json`):

**1. Antigravity (`gemini-antigravity`) - Primary Supplier for Gemini & Claude 4.6**
- **Models Supplied**: `gemini-2.0-flash`, `gemini-2.5-pro`, `gemini-3.0-pro`, `gemini-3.1-pro-high`, `gemini-3.1-pro-low`, `gemini-pro`, `claude-sonnet-4-6`, `claude-opus-4-6`
- **Fallback**: Gemini CLI for Gemini; Kiro for Claude

**2. Amazon Kiro (`claude-kiro-oauth`) - Primary Supplier for Claude 4.5 & Below**
- **Models Supplied**: `claude-sonnet-4-5`, `claude-opus-4-5`, `claude-haiku-3-5`
- **Fallback**: GitHub Models or Copilot Proxy

**3. Gemini CLI / AI Studio (`gemini-cli-oauth`) - Backup Supplier for Gemini**
- **Models Supplied**: `gemini-2.0-flash`, `gemini-2.5-flash`
- **Fallback**: GitHub Models, Paid OpenAI/Anthropic APIs.

**4. Qwen Code (`openai-qwen-oauth`) - Primary for Qwen**
- **Models Supplied**: `qwen3-coder-plus`, `qwen3-coder`
- **Fallback**: Direct Paid Providers

### B. Supplemental / Generalized Providers
When specific pools run dry, or for offering direct OpenAI models, the system leans on these powerful proxies:

**5. GitHub Models API (`github-models`) - Free General Multi-Model Proxy**
- Uses a GitHub PAT (`GITHUB_TOKEN`) to hit Microsoft's Azure managed inference tier. 
- **Models Provided**: `github-gpt-4o`, `github-claude-sonnet`, `github-gemini-pro`, `github-o4-mini`, `github-deepseek-v3`
- *Use Case*: Extremely reliable fallback for GPT-4o, Claude Sonnet, and Gemini Pro.

**6. GitHub Copilot Proxy (`copilot-api`) - Primary for OpenAI (GPT-4o)**
- Authenticates using a GitHub Copilot subscription via `ericc-ch/copilot-api` to act as an OpenAI/Anthropic proxy.
- **Models Provided**: `copilot-gpt-4o`, `copilot-claude-sonnet`, `copilot-o4-mini`

### C. Complete Fallback Chain (Circuit Breaker)
When a user requests a generic `"auto"` model or a model fails across its primary provider, the Circuit Breaker iterates through this priority queue:

2. **Antigravity (`gemini-antigravity`)**: Primary free tier for Gemini models.
3. **Gemini CLI (`gemini-cli-oauth`)**: Secondary backup free tier for Gemini models.
4. **Amazon Kiro (`claude-kiro-oauth`)**: Primary free tier for Claude models.
5. **Qwen Code (`openai-qwen-oauth`)**: Top tier for Qwen.
6. **GitHub Copilot Proxy (`copilot-api`)**: Primary supplier for GPT-4o outputs without using direct paid keys.
7. **GitHub Models (`github-models`)**: Last line of free-tier defense for GPT-4o, Sonnet, Gemini, and DeepSeek.
8. **Paid APIs (`openai-custom`, `openai-iflow`, `claude-custom`)**: Ultimate fallback using paid API keys to absolutely guarantee the response doesn't fail if all free accounts are exhausted. Margins become negative here, prioritizing customer retention over immediate profit per request.
