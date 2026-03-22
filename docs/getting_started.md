# Getting Started with AIKompute

Welcome to the AIKompute API platform! This guide will walk you through the process of creating an account, generating your first API key, and making your first API request.

## 1. Sign Up for an Account

To begin using our platform, you need to create an account:

1. Navigate to our [Sign Up page](https://aikompute.com/signup).
2. Enter your **Email Address** and choose a strong **Password**.
3. Read and accept the Terms of Service and Privacy Policy.
4. Click **Create Account**.
5. Check your email for a verification link and click it to verify your account.

## 2. Accessing the Dashboard

Once your email is verified, log in to the platform at [https://aikompute.com/login](https://aikompute.com/login). 

Upon logging in, you will be greeted by the **Dashboard**, your central hub for:
- Monitoring API usage
- Managing your generated API keys
- Accessing billing and account settings
- Viewing supported models

## 3. Generating Your First API Key

To authenticate your requests to our AI models, you must use an API key. 

1. On the Dashboard, navigate to the **API Keys** section in the left sidebar.
2. Click the **+ Create New Key** button.
3. Provide a recognizable name for your key (e.g., "Development", "Production App").
4. Click **Generate**.
5. **Important:** Copy your new API key and store it securely. For security reasons, you will not be able to see the full key again once you close this window.

## 4. Making Your First Request

AIKompute is fully compatible with OpenAI's API structure. This means you can use standard OpenAI libraries (like Python or Node.js) by simply changing the `base_url` and providing your AIKompute API key.

Here is an example using `curl`:

```bash
curl "https://api.aikompute.com/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -d '{
    "model": "gpt-3.5-turbo",
    "messages": [
      {
        "role": "system",
        "content": "You are a helpful assistant."
      },
      {
        "role": "user",
        "content": "Hello! What can you do?"
      }
    ]
  }'
```

Replace `YOUR_API_KEY` with the key you generated in the previous step.

## 5. Agent & IDE Setup Guides

To help you get started with your favorite AI tool, we've created specific, detailed guides for every major platform:

### Popular AI Agents
- **[Roo Code Setup Guide](guide_roo_code.md)**
- **[Cline Setup Guide](guide_cline.md)**
- **[OpenClaw Setup Guide](guide_openclaw.md)**
- **[Kilo Code Setup Guide](guide_kilocode.md)**
- **[Aider CLI Guide](guide_aider.md)**
- **[OpenCode Guide](guide_opencode.md)**
- **[Claude Code & Native CLIs](guide_native_clis.md)**

### AI-Native IDEs & Web Tools
- **[Cursor Setup Guide](guide_cursor.md)**
- **[Windsurf Setup Guide](guide_windsurf.md)**
- **[Continue.dev Setup Guide](guide_continue_dev.md)**
- **[Bolt.diy Setup Guide](guide_bolt_diy.md)**
- **[Vercel SDK & Chat Guide](guide_chat_vercel.md)**
- **[Trae / MarsCode Guide](guide_trae_marscode.md)**
- **[Warp Terminal Guide](guide_warp.md)**

### Enterprise & Other Extensions
- **[Codeium, Tabnine, Amazon Q Guide](guide_enterprise_extensions.md)**

### No-Code & Automation
- **[n8n, Make.com, Zapier Guide](guide_automation_tools.md)**
- **[Generic Tools Guide (AnythingLLM, etc.)](guide_generic_tools.md)**

---

## Next Steps

- Explore the [API Reference](api_reference.md) to see all supported endpoints and parameters.
- Check out [Use Cases](use_cases.md) to get inspiration for your next project.
- Read through the [Settings Management](settings_management.md) guide to learn how to manage your team and billing limits.
- If you need help, check our [FAQ](faq.md) or [Support Page](support_and_help.md).
