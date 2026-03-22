# Setup Guide: Windsurf IDE

This guide provides specific instructions for connecting the **Windsurf IDE (CodeWinds)** to the AIKompute AI Inference Gateway. 

Windsurf, like Cursor, uses the standard **OpenAI-compatible protocol** for its AI features.

---

## 1. Setup in Windsurf Settings

1. Open Windsurf and go to **Settings** (`Cmd + ,` or `Ctrl + ,`).
2. Navigate to **Integrations** or **AI** > **Model Provider**.
3. **Override the OpenAI Base URL**: 
   - Set the URL to: `https://aikompute.com/v1`
4. **Enter your API Key**: 
   - Input your AIKompute key (e.g., `sk-inf-...`).
5. **Add Models**: 
   - Ensure you toggle or add the following model names:
     - `gpt-4o`
     - `claude-sonnet-4-6`
     - `deepseek-v3`
     - `deepseek-r1`

---

## 2. Using Claude in Windsurf

Even though Windsurf use an OpenAI wrapper, AIKompute will automatically translate your requests to the Claude 3.5 Sonnet backend when you select it.

---

## Troubleshooting
If Windsurf reports a connection failure, double-check that your Base URL ends in `/v1`. Some versions of Windsurf check for a `/models` endpoint, which our gateway also provides.
