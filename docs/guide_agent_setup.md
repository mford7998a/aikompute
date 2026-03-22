# AI Agent Setup Guide (Roo Code / Cline / Cursor)

This guide provides specific instructions for connecting professional AI agent harnesses—like **Roo Code**, **Cline**, and **Cursor**—to the AIKompute AI Inference Gateway. 

By using our **Native Protocol Endpoints**, you get 100% reliable tool-calling and complex multi-step reasoning without the translation issues often found in generic OpenAI wrappers.

---

## 1. Anthropic / Claude Setup (Recommended)

To get the best performance from Claude 3.5 Sonnet or Opus inside Roo Code/Cline, use the **Native Anthropic Provider**. This ensures tool-calling schemas are sent in the native format.

### Settings in Roo Code / Cline:
- **API Provider**: `Anthropic`
- **Base URL**: `https://aikompute.com`
- **Anthropic API Key**: `YOUR_AIKOMPUTE_API_KEY` (e.g., `sk-inf-...`)
- **Model ID**: `claude-sonnet-4-6` or `claude-3-5-sonnet`

> [!TIP]
> Even though you are selecting the "Anthropic" provider, our gateway will authenticate your AIKompute key and route the request to the high-performance backend automatically.

---

## 2. Google Gemini Setup (Native)

For ultra-fast responses and massive context windows (up to 2M tokens), use the **Native Gemini Provider**.

### Settings in Roo Code / Cline:
- **API Provider**: `Gemini`
- **Base URL**: `https://aikompute.com`
- **Gemini API Key**: `YOUR_AIKOMPUTE_API_KEY`
- **Model ID**: `gemini-2.5-pro` or `gemini-2.0-flash`

---

## 3. OpenAI / DeepSeek / Qwen Setup (Generic)

For standard text-generation models, use the universal OpenAI-compatible endpoint.

### Settings in Roo Code / Cline:
- **API Provider**: `OpenAI Compatible`
- **Base URL**: `https://aikompute.com/v1`
- **API Key**: `YOUR_AIKOMPUTE_API_KEY`
- **Model ID**: 
  - `gpt-4o` (OpenAI)
  - `deepseek-v3` (DeepSeek)
  - `deepseek-r1` (DeepSeek Reasoning)
  - `qwen3-coder-plus` (Alibaba Qwen)

---

## 4. Key Differences & Endpoints

| Protocol | Base URL | Header Used | Best For |
| :--- | :--- | :--- | :--- |
| **Anthropic** | `https://aikompute.com` | `x-api-key` | Roo Code, Cline (Claude Models) |
| **Gemini** | `https://aikompute.com` | `(URL Param)` | Native Gemini SDKs |
| **OpenAI** | `https://aikompute.com/v1` | `Authorization: Bearer` | Cursor, AnythingLLM, Dify |

---

## Troubleshooting

### "Model Response Incomplete"
If you see an "Incomplete Response" error in Roo Code after setup, verify:
1. You have **not** added `/v1` to the Base URL if you chose the "Anthropic" provider.
2. Your account balance is greater than zero on the [AIKompute Dashboard](https://aikompute.com).
3. Your key is not restricted to a specific IP address that doesn't match your current location.

### Tools failing in Claude
Ensure you are using the **Native Anthropic** provider as described in Section 1. If you use "OpenAI Compatible" for Claude models, tool-call XML tags (`<invoke>`) may occasionally leak into the output. 
