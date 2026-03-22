# Setup Guide: Bolt (Bolt.diy, Bolt.new)

This guide provides specific instructions for connecting **Bolt.diy** (the open-source version of bolt.new) to the AIKompute AI Inference Gateway. 

Bolt is a web development agent that works with multiple protocols for high-fidelity code generation.

---

## 1. Native Anthropic Protocol (Recommended for Claude)

Use this for the best reliability when coding with Claude 3.5 Sonnet.

### Settings in Bolt.diy:
- **Provider**: `Anthropic`
- **Base URL**: `https://aikompute.com`
- **Anthropic API Key**: `YOUR_AIKOMPUTE_API_KEY`
- **Model ID**: `claude-sonnet-4-6`

---

## 2. Native Gemini Protocol

For ultra-fast responses and large context windows.

### Settings in Bolt.diy:
- **Provider**: `Gemini`
- **Base URL**: `https://aikompute.com`
- **Gemini API Key**: `YOUR_AIKOMPUTE_API_KEY`
- **Model ID**: `gemini-2.5-pro`

---

## 3. OpenAI-Compatible Protocol

For standard models like GPT-4o, DeepSeek, and Qwen.

### Settings in Bolt.diy:
- **Provider**: `OpenAI Compatible`
- **Base URL**: `https://aikompute.com/v1`
- **API Key**: `YOUR_AIKOMPUTE_API_KEY`
- **Model ID**: `gpt-4o`

---

## Troubleshooting
If Bolt.diy reports an error with model ID, ensure you select the model name that matches the provider. For example, don't use the `openai` provider with a `claude-` model ID.
