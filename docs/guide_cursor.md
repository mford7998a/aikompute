# Setup Guide: Cursor

This guide provides specific instructions for connecting **Cursor (The AI Code Editor)** to the AIKompute AI Inference Gateway. 

Cursor uses the **OpenAI-compatible protocol** for its predictions and chat features.

---

## 1. Setup in Cursor Settings

1. Open Cursor and go to **Settings** (`Cmd + ,` or `Ctrl + ,`).
2. Navigate to **Models** > **OpenAI API Key**.
3. **Override the Base URL**: 
   - Set the URL to: `https://aikompute.com/v1`
4. **Enter your API Key**: 
   - Input your AIKompute key (e.g., `sk-inf-...`).
5. **Add Models**: 
   - Ensure the following model names are added to your list:
     - `gpt-4o`
     - `claude-sonnet-4-6`
     - `deepseek-v3`
     - `deepseek-r1`

---

## 2. Using Claude in Cursor

Even though Cursor uses an OpenAI wrapper, AIKompute will automatically translate your requests to the Claude 3.5 Sonnet backend when you select it.

### Settings:
- **Base URL**: `https://aikompute.com/v1`
- **Model Name**: `claude-sonnet-4-6`

---

## Troubleshooting
If Cursor reports "Invalid API Key", verify you have added the `/v1` suffix to the Base URL. Unlike Roo Code or Cline, Cursor always expects the OpenAI-compatible endpoint.
