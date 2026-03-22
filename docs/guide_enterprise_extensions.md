# Setup Guide: Codeium, Tabnine, and Amazon Q (Custom Models)

This guide provides specific instructions for connecting **Codeium**, **Tabnine**, and **Amazon Q** to the AIKompute AI Inference Gateway as custom AI model providers. 

These extensions typically default to their own proprietary models, but can be configured to use your AIKompute credentials for more powerful models like Claude 3.5 Sonnet or GPT-4o.

---

## 1. Native Anthropic Protocol (Recommended for Claude)

Use this for the best reliability when coding with Claude 3.5 Sonnet.

### Settings:
- **Provider**: `Anthropic`
- **Base URL**: `https://aikompute.com`
- **API Key**: `YOUR_AIKOMPUTE_API_KEY`
- **Model ID**: `claude-sonnet-4-6`

---

## 2. Native Gemini Protocol

For ultra-fast responses and large context windows.

### Settings:
- **Provider**: `Gemini`
- **Base URL**: `https://aikompute.com`
- **API Key**: `YOUR_AIKOMPUTE_API_KEY`
- **Model ID**: `gemini-2.5-pro`

---

## 3. OpenAI-Compatible Protocol

For standard models like GPT-4o, DeepSeek, and Qwen.

### Settings:
- **Provider**: `OpenAI Compatible`
- **Base URL**: `https://aikompute.com/v1`
- **API Key**: `YOUR_AIKOMPUTE_API_KEY`
- **Model ID**: `gpt-4o`

---

## Troubleshooting
If the extension reports "Invalid API Key", verify that you have chosen the correct provider type. Most extensions will expect different authentication headers for each protocol.
