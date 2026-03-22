# Setup Guide: Kilo Code

This guide provides specific instructions for connecting **Kilo Code** (Kilo AI) to the AIKompute AI Inference Gateway. 

Kilo Code is an AI agent that works flawlessly with AIKompute by changing the base URL.

---

## 1. Setup in Kilo Code Settings

1. Find the **Custom Model** or **OpenAI API Key** field.
2. Set the **API Base URL**: 
   - Set the URL to: `https://aikompute.com/v1`
3. Enter your **AIKompute Key**: 
   - Input your key (e.g., `sk-inf-...`).
4. **Add Models**: 
   - Enter your preferred model (e.g., `gpt-4o`, `claude-sonnet-4-6`).

---

## 2. Using Claude in Kilo Code

Even though Kilo Code uses an OpenAI wrapper, AIKompute will automatically translate your requests to the Claude 3.5 Sonnet backend when you select it.

---

## Troubleshooting
If Kilo Code reports "Invalid API Key", verify you have added the `/v1` suffix to the Base URL. Like most VS Code extensions, Kilo Code expects the standard OpenAI-compatible endpoint.
