# Feature: AI Chat Backend & LLM Integration

## /specify prompt

```
Build the Python AI conversational search service with LLM provider abstraction, prompt management, and visual references.

## What
1. AI Chat Service (Python): gRPC service implementing AIChatService with bidirectional streaming Chat RPC. Manages conversation state in Redis. Each conversation tracks: session_id, user_id, language, message history, current criteria_state (structured JSON), turn count.

2. LLM Provider Abstraction: BaseLLMProvider interface with generate(messages, system_prompt) → stream[tokens]. Implementations: ClaudeProvider (Anthropic SDK, streaming), OpenAIProvider (OpenAI SDK, streaming), LiteLLMProvider (any model via LiteLLM, for self-hosted Llama/Mistral). Active provider configurable via env var LLM_PROVIDER. Fallback to secondary provider on error.

3. System Prompt: Jinja2 template defining the AI's role as expert real estate advisor. Injects: available property types per country, available countries and zones, user's language, progressive refinement flow instructions (10 dimensions), output format (chat message + JSON criteria + optional visual trigger + suggested chips).

4. Market Context Injection: before each LLM call, fetch zone median prices, deal counts, and listing volume via gRPC to api-gateway. Inject as structured data block in prompt.

5. Criteria State Parser: parse LLM response into components (chat_message, criteria_json, visual_trigger, chips). Validate criteria against platform taxonomy. Handle malformed output gracefully.

6. Visual Reference Library: curated image collection organized by tags (style, feature, type). 200+ royalty-free images. Query API by tags returns 4-5 images.

7. Criteria Finalization: when criteria complete → convert to search query → call Listings API → return results + auto-create alert rule.

8. Subscription limits: Free 3 conversations/day (10 turns), Basic 10/day (20 turns), Pro+ unlimited.

## Acceptance Criteria
- Full conversation flow: user message → LLM response with criteria JSON → progressive refinement → summary card → search + alert
- Works with Claude, GPT-4o, and Llama-3 via LiteLLM
- Streaming response appears token-by-token
- Market context (zone prices, deal counts) injected correctly and used by AI
- Visual references triggered when user mentions style preferences
- Criteria JSON valid and matches platform taxonomy for all test conversations
- Subscription limits enforced (403 when exceeded)
- Conversation state persists across reconnections
```
