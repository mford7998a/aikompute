# Setup Guide: Aider (CLI Agent)

This guide provides specific instructions for connecting the **Aider CLI** to the AIKompute AI Inference Gateway. 

Aider is one of the most popular AI pair-programming tools and it works flawlessly with AIKompute by setting your environment variables correctly.

---

## 1. Setup in Environment Variables

Aider uses specific environment variables to configure its API key and base URL.

### For OpenAI-compatible models (e.g., GPT-4o, DeepSeek):
1. Create a `.env` file in your project or export these values globally:
   - `OPENAI_API_KEY=YOUR_AIKOMPUTE_API_KEY`
   - `OPENAI_API_BASE=https://api.aikompute.com/v1`
2. Run Aider: `aider --model openrouter/deepseek/deepseek-chat` (or similar).

### For Native Claude (Recommended):
1. Export these values:
   - `ANTHROPIC_API_KEY=YOUR_AIKOMPUTE_API_KEY`
   - `ANTHROPIC_API_BASE=https://api.aikompute.com`
2. Run Aider: `aider --model anthropic/claude-3-5-sonnet-20240620`

---

## 2. Using Claude in Aider

Aider is excellent at exploiting Claude's strengths. We recommend using the **Native Anthropic Base URL** as shown in Section 1. This ensures that Aider's sophisticated prompting and tool-coding instructions arrive exactly as intended.

---

## Troubleshooting
If Aider says "Model Not Found", verify that the model ID you are passing exactly matches what is listed in the [AIKompute Models List](https://api.aikompute.com/v1/models).
