# Use Cases

The AIKompute platform provides access to a variety of state-of-the-art models for different tasks. Here is an overview of common use cases and how to implement them.

## 1. Conversational Chatbots

Building AI companions, customer support bots, or interactive tutors.

**Recommended Models:**
- `gpt-3.5-turbo` (cost-effective)
- `gpt-4o` (highly capable, multimodal)
- `claude-3-opus-20240229` (highly capable, natural writing style)

**Implementation Strategy:**
Maintain a history of the conversation in the `messages` array. Keep a persistent `system` message at the beginning to define the bot's persona and rules.

## 2. Data Extraction and Structuring

Pulling specific data fields (like names, dates, amounts) out of unstructured text (like emails, articles, or PDFs).

**Recommended Models:**
- `gpt-4-turbo` 
- `claude-3-sonnet-20240229`

**Implementation Strategy:**
Use a detailed `system` prompt restricting the model to reply **only** in JSON format. Provide an exact JSON schema for the model to follow.

## 3. Content Summarization

Condensing long articles, meeting transcripts, or reports into brief overviews.

**Recommended Models:**
- `claude-3-haiku-20240307` (fast and cheap for long context)
- `qwen-turbo`

**Implementation Strategy:**
Pass the entire text as a `user` message with the instruction: "Summarize the following text into 3 bullet points."

## 4. Code Generation and Review

Writing functions, generating unit tests, or identifying bugs in existing code.

**Recommended Models:**
- `gpt-4o`
- `claude-3-opus-20240229`

**Implementation Strategy:**
Provide the language context and detailed requirements. For code review, provide the diff or the troubled function alongside the specific error output.

## 5. Translation and Localization

Translating user interfaces, marketing material, or user-generated content into multiple languages.

**Recommended Models:**
- `gpt-3.5-turbo`

**Implementation Strategy:**
Use a system prompt like "You are a professional translator. Translate the following English text to French, keeping the tone professional but approachable."
