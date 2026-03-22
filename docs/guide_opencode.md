# Setup Guide: OpenCode (VS Code Extension)

This guide provides specific instructions for connecting the **OpenCode** extension for VS Code to the AIKompute AI Inference Gateway. 

OpenCode works flawlessly by changing the base URL.

---

## 1. Setup in OpenCode Settings

1. Open VS Code and go to **Settings** (`Cmd + ,` or `Ctrl + ,`).
2. Search for `OpenCode` and find the **Custom Model** or **OpenAI API Key** field.
3. **Override the API Base URL**: 
   - Set the URL to: `https://aikompute.com/v1`
4. **Enter your AIKompute Key**: 
   - Input your key (e.g., `sk-inf-...`).
5. **Add Models**: 
   - Enter your preferred model (e.g., `gpt-4o`, `claude-sonnet-4-6`).

---

## 2. Using Claude in OpenCode

Even though OpenCode uses an OpenAI wrapper, AIKompute will automatically translate your requests to the Claude 3.5 Sonnet backend when you select it.

---

## Troubleshooting
If OpenCode reports "Invalid API Key", verify you have added the `/v1` suffix to the Base URL. Like most VS Code extensions, OpenCode expects the standard OpenAI-compatible endpoint.
