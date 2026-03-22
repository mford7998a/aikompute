# Setup Guide: OpenClaw

This guide provides specific instructions for connecting **OpenClaw** to the AIKompute AI Inference Gateway. 

OpenClaw is an open-source tool for Claude that works with both OpenAI-compatible and Native Anthropic protocols.

---

## 1. Native Anthropic Protocol (Recommended)

To get the best performance from Claude 3.5 Sonnet or Opus, use the native protocol.

### Settings:
- **API Provider**: `Anthropic`
- **Base URL**: `https://aikompute.com`
- **Anthropic API Key**: `YOUR_AIKOMPUTE_API_KEY` (e.g., `sk-inf-...`)
- **Model ID**: `claude-sonnet-4-6` or `claude-3-5-sonnet`

---

## 2. OpenAI-Compatible Protocol

For standard GPT-4o, DeepSeek, or Qwen models.

### Settings:
- **API Provider**: `OpenAI Compatible`
- **Base URL**: `https://aikompute.com/v1`
- **API Key**: `YOUR_AIKOMPUTE_API_KEY`
- **Model ID**: `gpt-4o`, `deepseek-v3`, or `qwen3-coder-plus`

---

## Troubleshooting
If OpenClaw reports an error with model ID, ensure you select the model name that matches the provider. For example, don't use the `openai` provider with a `claude-` model ID.
