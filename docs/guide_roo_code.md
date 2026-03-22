# Setup Guide: Roo Code

This guide provides specific instructions for connecting **Roo Code** to the AIKompute AI Inference Gateway. 

Using the **Native Anthropic Provider** in Roo Code ensures 100% reliable tool-calling and eliminates extra XML noise in Claude responses.

---

## 1. Claude Mode (Recommended)

To get the best performance from Claude 3.5 Sonnet or Opus, use the native protocol.

### Settings:
- **API Provider**: `Anthropic`
- **Base URL**: `https://aikompute.com`
- **Anthropic API Key**: `YOUR_AIKOMPUTE_API_KEY` (e.g., `sk-inf-...`)
- **Model ID**: `claude-sonnet-4-6` or `claude-3-5-sonnet`

> [!NOTE]
> Do NOT add `/v1` to the base URL when using the Anthropic provider. Our gateway automatically identifies native Anthropic requests and handles your AIKompute key as the `x-api-key` header.

---

## 2. Gemini Mode (Native)

For large context window support, use the native Gemini provider.

### Settings:
- **API Provider**: `Gemini`
- **Base URL**: `https://aikompute.com`
- **Gemini API Key**: `YOUR_AIKOMPUTE_API_KEY`
- **Model ID**: `gemini-2.5-pro` or `gemini-2.0-flash`

---

## 3. OpenAI / Generic Mode

For standard GPT-4o, DeepSeek, or Qwen models.

### Settings:
- **API Provider**: `OpenAI Compatible`
- **Base URL**: `https://aikompute.com/v1`
- **API Key**: `YOUR_AIKOMPUTE_API_KEY`
- **Model ID**: `gpt-4o`, `deepseek-v3`, or `qwen3-coder-plus`

---

## Troubleshooting
If you see **"Model Response Incomplete"**, double-check that your Base URL does not end in `/v1` for the Anthropic/Gemini providers. The `/v1` suffix is ONLY for the "OpenAI Compatible" provider.
