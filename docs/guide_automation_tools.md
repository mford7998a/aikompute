# Setup Guide: n8n, Make.com, and Zapier

This guide provides specific instructions for connecting the **n8n**, **Make.com**, and **Zapier** to the AIKompute AI Inference Gateway. 

Most of these tools work perfectly by changing the base URL.

---

## 1. Setup in n8n (OpenAI-Compatible Node)

To use AIKompute in n8n, use the **OpenAI Chat Model Node**.

### Settings:
- **API Base URL**: `https://aikompute.com/v1`
- **Method**: `POST`
- **Body**: Standard OpenAI-compatible format.
- **Model ID**: `gpt-4o` or `claude-sonnet-4-6`.

---

## 2. Setup in Make.com (OpenAI-Compatible Module)

Use the **OpenAI Integration** in Make.com.

### Settings:
- **Provider**: `Custom OpenAI`
- **Base URL**: `https://aikompute.com/v1`
- **API Key**: `YOUR_AIKOMPUTE_API_KEY`
- **Model ID**: `gpt-4o` or `claude-sonnet-4-6`.

---

## 3. Setup in Zapier (OpenAI-Compatible Zap)

Use the **Zapier "OpenAI Integration"** or **WebAI Module**.

### Settings:
- **Provider**: `OpenAI Compatible`
- **Base URL**: `https://aikompute.com/v1`
- **API Key**: `YOUR_AIKOMPUTE_API_KEY`
- **Model ID**: `gpt-4o` or `claude-sonnet-4-6`.

---

## Troubleshooting
If the automation tool reports an "Invalid API Key", ensure you are using the correct Base URL and that your AIKompute key is correctly formatted.
