# API Reference

AIKompute is a high-performance AI inference gateway. While we are primarily **OpenAI-compatible**, we ALSO support **Native Native Protocols** for Anthropic and Google Gemini to provide the best possible experience for advanced AI agents like Roo Code and Cline.

---

## Base URLs & Protocols

| Use Case | Protocol | Base URL | Auth Header |
| :--- | :--- | :--- | :--- |
| **Standard OpenAI** | OpenAI Chat | `https://aikompute.com/v1` | `Authorization: Bearer <key>` |
| **Native Anthropic** | Anthropic Messages | `https://aikompute.com` | `x-api-key: <key>` |
| **Native Gemini** | Google Generative AI | `https://aikompute.com` | `?key=<key>` (URL Param) |

---

## 1. OpenAI Chat Completions (Standard)
`POST /v1/chat/completions`

Universal endpoint compatible with standard OpenAI client libraries.

**Example Request:**
```bash
curl https://aikompute.com/v1/chat/completions \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -d '{
    "model": "gpt-4o",
    "messages": [{"role": "user", "content": "Hello!"}],
    "stream": true
  }'
```

---

## 2. Native Anthropic Messages
`POST /v1/messages`

Designed for advanced users and agents (Roo Code, Cline) who need native Claude tool-calling and response formats.

**Example Request:**
```bash
curl https://aikompute.com/v1/messages \
  -H "x-api-key: YOUR_API_KEY" \
  -H "anthropic-version: 2023-06-01" \
  -d '{
    "model": "claude-sonnet-4-6",
    "max_tokens": 1024,
    "messages": [{"role": "user", "content": "hi"}],
    "stream": true
  }'
```

---

## 3. Native Gemini Content
`POST /v1beta/models/{model}:generateContent`
`POST /v1beta/models/{model}:streamGenerateContent`

Compatible with Google's direct Gemini API structure.

**Example Request (Streaming):**
```bash
curl https://aikompute.com/v1beta/models/gemini-2.5-pro:streamGenerateContent?key=YOUR_API_KEY&alt=sse \
  -d '{
    "contents": [{"parts": [{"text": "Explain quantum physics"}]}]
  }'
```

---

## 4. Models List
`GET /v1/models`

Lists all models available on the gateway, including provider ownership and capabilities.

---

## Rate Limits & Billing
- **Billing**: Tokens are metered and billed to your PostGreSQL balance in real-time.
- **Limits**: Standard keys are limited to **500 RPM**. Master keys have unlimited throughput.
- **Errors**: `429 Too Many Requests` indicates you have hit a rate limit. `402 Payment Required` indicates zero credit balance.
