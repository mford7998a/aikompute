# Setup Guide: Vercel AI Chat & Vercel SDK

This guide provides specific instructions for connecting the **Vercel AI SDK** and **Vercel AI Chat** to the AIKompute AI Inference Gateway. 

Vercel's SDK is very flexible and supports all three protocols for building your own AI interfaces.

---

## 1. Native Anthropic Protocol (Recommended for Claude)

Use this for the best reliability when coding with Claude 3.5 Sonnet.

### Settings:
- **Provider**: `createAnthropic`
- **Base URL**: `https://aikompute.com`
- **API Key**: `YOUR_AIKOMPUTE_API_KEY`
- **Model ID**: `claude-sonnet-4-6`

---

## 2. Native Gemini Protocol

For ultra-fast responses and large context windows.

### Settings:
- **Provider**: `createGoogleGenerativeAI`
- **Base URL**: `https://aikompute.com`
- **API Key**: `YOUR_AIKOMPUTE_API_KEY`
- **Model ID**: `gemini-2.5-pro`

---

## 3. OpenAI-Compatible Protocol

For standard models like GPT-4o, DeepSeek, and Qwen.

### Settings:
- **Provider**: `createOpenAI`
- **Base URL**: `https://api.aikompute.com/v1`
- **API Key**: `YOUR_AIKOMPUTE_API_KEY`
- **Model ID**: `gpt-4o`

---

## Troubleshooting
If the Vercel AI SDK reports an invalid response type, ensure you are using the correct `media_type` when streaming from our native endpoints.
