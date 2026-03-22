# Setup Guide: Other Agents & Tools (Dify, AnythingLLM, Open-WebUI)

This guide provides specific instructions for connecting **Dify**, **AnythingLLM**, **Open-WebUI**, and other generic AI platforms to the AIKompute AI Inference Gateway. 

Most of these tools use the **OpenAI-compatible protocol** for and work perfectly by changing the base URL.

---

## 1. Setup in Settings

1. Find the **LLM Provider** or **Custom OpenAI Provider** section.
2. Set the **Base URL**: 
   - Set the URL to: `https://aikompute.com/v1`
3. Enter your **AIKompute API Key**: 
   - Input your key (e.g., `sk-inf-...`).
4. Select or Add **Models**: 
   - Use standard names like:
     - `gpt-4o` (OpenAI)
     - `claude-sonnet-4-6` (Claude)
     - `deepseek-v3` (DeepSeek)
     - `deepseek-r1` (DeepSeek Reasoning)
     - `qwen3-coder-plus` (Qwen)

---

## 2. Using Claude in Generic Tools

Even though these tools use an OpenAI wrapper, AIKompute will automatically handle the translation your requests to the Claude 3.5 Sonnet backend when you select it.

### Settings:
- **Base URL**: `https://aikompute.com/v1`
- **Model ID**: `claude-sonnet-4-6`

---

## Troubleshooting
If the tool reports "Invalid Model", ensure you have spelled the model name exactly as it appears in the [AIKompute Models List](https://aikompute.com/v1/models).
