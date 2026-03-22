# Setup Guide: Continue.dev

This guide provides specific instructions for connecting the **Continue.dev** (VS Code / JetBrains extension) to the AIKompute AI Inference Gateway. 

Continue is one of the most flexible extensions and it supports all three of our gateway's native and compatible protocols.

---

## 1. Native Anthropic Protocol (Recommended for Claude)

Use this for the best reliability when coding with Claude 3.5 Sonnet.

### `config.json` Settings:
```json
{
  "models": [
    {
      "title": "Claude 3.5 Sonnet (Native)",
      "provider": "anthropic",
      "model": "claude-sonnet-4-6",
      "apiKey": "YOUR_AIKOMPUTE_API_KEY",
      "apiBase": "https://aikompute.com"
    }
  ]
}
```

---

## 2. Native Gemini Protocol

For ultra-fast responses and large context windows.

### `config.json` Settings:
```json
{
  "models": [
    {
      "title": "Gemini 2.5 Pro (Native)",
      "provider": "gemini",
      "model": "gemini-2.5-pro",
      "apiKey": "YOUR_AIKOMPUTE_API_KEY",
      "apiBase": "https://aikompute.com"
    }
  ]
}
```

---

## 3. OpenAI-Compatible Protocol

For standard models like GPT-4o, DeepSeek, and Qwen.

### `config.json` Settings:
```json
{
  "models": [
    {
      "title": "GPT-4o (OpenAI)",
      "provider": "openai",
      "model": "gpt-4o",
      "apiKey": "YOUR_AIKOMPUTE_API_KEY",
      "apiBase": "https://aikompute.com/v1"
    }
  ]
}
```

---

## Troubleshooting
If Continue.dev reports an error connection during indexing, ensure your API key has enough credits.
