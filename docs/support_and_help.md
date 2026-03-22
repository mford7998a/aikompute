# Support & Help

If you're stuck, experiencing difficulties, or just have a general question, the AIKompute support team is here to assist you.

## Resolving Common Issues

Before reaching out, check our documentation to see if your question is already answered:
- Need to know how to connect? See [Getting Started](getting_started.md).
- Seeking endpoint details? See the [API Reference](api_reference.md).
- Have a question about billing? See the [FAQ](faq.md) and [Settings Management](settings_management.md).

### Common Errors

- **401 Unauthorized**: Your API key is invalid, missing, or has been revoked. Create a new key in the Dashboard.
- **429 Too Many Requests**: You are sending queries faster than your rate limit allows. Implement retries with exponential backoff.
- **402 Payment Required**: Your account balance is out of funds. Add funds in the Billing section to resume services.
- **502 Bad Gateway / Upstream Error**: The backend model provider (e.g., OpenAI, Anthropic) is currently experiencing issues. Our status page dynamically tracks upstream health.

## Contacting Support

If you need hands-on help, please provide us with as much context as possible.

### Community Support
Join our Discord Server to connect with other developers, share projects, and ask questions. Our team actively monitors the help channels.
- **Discord**: [Join the AIKompute Community](https://discord.gg/example)

### Email Support
For account-specific issues, billing inquiries, or technical problems not resolvable via Discord:
- **Email**: support@aikompute.com
- **Expected Response Time**: 1-2 business days for Free tier, 4 hours for Pro.

**When emailing, please include:**
1. Your account email address.
2. The specific model you were trying to query.
3. The exact error message or HTTP status code you received.
4. A code snippet showing you how you make the request (ensure you **redact your API key** before sending!).

## System Status
If you suspect an outage, check our status page at [status.aikompute.com](https://status.aikompute.com). This page is updated in real-time and provides information on system-wide incidents and degraded performance from upstream model providers.
