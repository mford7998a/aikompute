# Setup Guide: Trae / MarsCode

This guide provides specific instructions for connecting **Trae** and **MarsCode** to the AIKompute AI Inference Gateway. 

Because Trae and MarsCode use a non-standard internal proxy structure, AIKompute handles them differently by routing requests through a specialized **WebAI2API** bridge.

---

## 1. Setup in Trae / MarsCode Settings

1. Find the **Custom Model** or **OpenAI API** settings.
2. Set the **Base URL**: 
   - Set the URL to: `https://aikompute.com/v1`
3. Enter your **AIKompute API Key**: 
   - Input your key (e.g., `sk-inf-...`).
4. Select or Add **Models**: 
   - Use standard model names (e.g., `gpt-4o`, `claude-3-5-sonnet`).

---

## 2. Using Claude in Trae / MarsCode

Our gateway will automatically translate your requests into the correct format for Trae and MarsCode's backend servers.

---

## Troubleshooting
If you see a "Connection Refused" error, double-check that your Base URL ends in `/v1`. Some versions of Trae try to strip the path suffix, so ensure the full URL is correct in your configuration file.
