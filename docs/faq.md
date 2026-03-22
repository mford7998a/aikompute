# Frequently Asked Questions (FAQ)

## Account & Access

### Is there a free trial?
Yes, new users immediately receive a starting credit balance upon email verification. This allows you to test out various models and our platform's latency before adding a credit card.

### Can I run this locally?
Our public API runs on the cloud. However, the core proxy logic is open-source. For self-hosted solutions, please contact our Enterprise team.

## Usage & Billing

### How am I charged?
You are charged strictly based on usage (per 1,000 tokens processed). Different models have different pricing for Prompt (input) and Completion (output) tokens. You can view the pricing breakdown on your Dashboard.

### What happens if I go over my limit?
If you hit your configured Hard Limit or run out of pre-funded balance, the API will start returning a `402 Payment Required` or `429 Too Many Requests` error. Make sure to set up auto-recharge and soft limit alerts to prevent downtime.

### Do failed requests still incur a cost?
No. If the platform returns a 5xx or 4xx error (other than standard completions like a filtered response), you will not be charged. Only successful generations consuming tokens apply to your balance.

## Technical

### Which models do you support?
We support a rapidly expanding roster including:
- OpenAI (GPT-3.5, GPT-4, GPT-4o)
- Anthropic (Claude 3 Haiku, Sonnet, Opus)
- OpenRouter free/paid models
- Select open-source models (Llama 3, Qwen)
You can always query the `GET /v1/models` endpoint for the live list.

### Is AIKompute compatible with the OpenAI SDK?
Yes! Our endpoint is fully compatible with the standard OpenAI SDK format. All you need to do is change the `base_url` to `https://api.aikompute.com/v1` and use our generated API key.

### Are my prompts used for model training?
No. We do not use user prompt data or completions for training our own models, nor do we pass permission for upstream providers (like OpenAI or Anthropic) to train on your data when accessed through our gateway.

## Privacy & Security

### Where is my data processed?
Our primary infra is hosted on Google Cloud Platform (GCP). Requests are securely proxied to the target AI providers across encrypted connections. 

### Can I delete my account?
Yes, you can initiate account deletion from the Settings page. Upon deletion, your data and remaining credits are immediately removed.
