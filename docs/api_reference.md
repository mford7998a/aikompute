# API Reference

The AIKompute API is designed to be a drop-in fully compatible replacement for the standard OpenAI API format. You can use standard libraries (e.g., `openai` in Python/Node.js) simply by pointing the base URL to our gateway.

## Base URL

All API requests should be routed completely relative to the following base URL:

```text
https://api.aikompute.com/v1
```

## Authentication

Identify yourself by including an `Authorization` header with your API key as a Bearer token in all HTTP requests.

```text
Authorization: Bearer YOUR_API_KEY
```

## Endpoints

### 1. Chat Completions
`POST /v1/chat/completions`

Generates a model response for the given chat conversation.

**Request Body parameters:**
- `model` (string, required): ID of the model to use (e.g., `gpt-3.5-turbo`, `claude-3-haiku-20240307`).
- `messages` (array, required): A list of messages comprising the conversation so far.
  - `role` (string): The role of the messages author (system, user, assistant).
  - `content` (string): The contents of the message.
- `temperature` (number, optional): What sampling temperature to use, between 0 and 2. Default is 1.
- `max_tokens` (integer, optional): The maximum number of tokens to generate in the chat completion.
- `stream` (boolean, optional): If set, partial message deltas will be sent.

**Example Request:**
```json
{
  "model": "gpt-3.5-turbo",
  "messages": [{"role": "user", "content": "Tell me a joke."}],
  "temperature": 0.7
}
```

**Example Response:**
```json
{
  "id": "chatcmpl-123",
  "object": "chat.completion",
  "created": 1677652288,
  "model": "gpt-3.5-turbo",
  "choices": [{
    "index": 0,
    "message": {
      "role": "assistant",
      "content": "Why did the chicken cross the road? To get to the other side!"
    },
    "finish_reason": "stop"
  }],
  "usage": {
    "prompt_tokens": 12,
    "completion_tokens": 14,
    "total_tokens": 26
  }
}
```

### 2. Models list
`GET /v1/models`

Lists the currently available models, and provides basic information about each one such as the owner and availability.

**Example Response:**
```json
{
  "object": "list",
  "data": [
    {
      "id": "gpt-3.5-turbo",
      "object": "model",
      "created": 1677610602,
      "owned_by": "openai"
    },
    {
      "id": "claude-3-opus-20240229",
      "object": "model",
      "created": 1709251200,
      "owned_by": "anthropic"
    }
  ]
}
```

## Rate Limits
Your API usage is subject to rate limiting to preserve system stability. Rate limits vary depending on your account tier.
- **Free Tier:** 10 requests per minute (RPM)
- **Pro Tier:** 500 RPM
- **Enterprise:** Custom limits

If you exceed a rate limit, the API will respond with a `429 Too Many Requests` status code. You should implement exponential backoff to handle these responses gracefully.
