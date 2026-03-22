# Setup Guide: Warp AI

This guide provides specific instructions for connecting the **Warp Terminal's AI features** to the AIKompute AI Inference Gateway. 

Warp AI uses the standard **OpenAI-compatible protocol** for its chat, command search, and debugging features.

---

## 1. Setup in Warp Settings

1. Open Warp and go to **Settings** (`Cmd + ,` or `Ctrl + ,`).
2. Navigate to **Integrations** or **AI** > **Custom Model**.
3. **Override the OpenAI Base URL**: 
   - Set the URL to: `https://aikompute.com/v1`
4. **Enter your API Key**: 
   - Input your AIKompute key (e.g., `sk-inf-...`).
5. **Add Models**: 
   - Select the model you want to use (e.g., `gpt-4o`, `deepseek-v3`).

---

## 2. Warp AI Models

Warp supports custom models like GPT-4o and Claude 3.5 Sonnet. To use them through AIKompute:
- **Base URL**: `https://aikompute.com/v1`
- **Model ID**: `gpt-4o` or `claude-sonnet-4-6`

---

## Troubleshooting
If Warp says "Model Not Found", verify you have spelled the model name exactly as it appears in the [AIKompute Models List](https://aikompute.com/v1/models).
