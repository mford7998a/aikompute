# Setup Guide: Claude Code CLI & Native CLIs

This guide provides specific instructions for connecting the **Claude Code CLI** (from Anthropic) and other native CLIs to the AIKompute AI Inference Gateway. 

Because we support native protocols, you can use these sophisticated CLI tools without any translation layers.

---

## 1. Native Anthropic Protocol (for Claude Code CLI)

Use this for the best reliability when coding with the tool.

### Settings:
- **Environment Variable**: `ANTHROPIC_API_KEY=YOUR_AIKOMPUTE_API_KEY`
- **Environment Variable**: `ANTHROPIC_BASE_URL=https://aikompute.com`
- **Model ID**: `claude-sonnet-4-6`

---

## 2. Native Gemini Protocol (for Gemini CLI)

For ultra-fast responses and large context windows.

### Settings:
- **Environment Variable**: `GOOGLE_API_KEY=YOUR_AIKOMPUTE_API_KEY`
- **Base URL**: `https://aikompute.com`
- **Model ID**: `gemini-2.5-pro`

---

## 3. OpenAI-Compatible Protocol (for OpenAI Codex & CLI)

For standard OpenAI models.

### Settings:
- **Environment Variable**: `OPENAI_API_KEY=YOUR_AIKOMPUTE_API_KEY`
- **Environment Variable**: `OPENAI_BASE_URL=https://aikompute.com/v1`
- **Model ID**: `gpt-4o`

---

## Troubleshooting
If the CLI reports a connection failure, verify that you have exported the environment variables in your current terminal session.
