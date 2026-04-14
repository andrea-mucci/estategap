# Feature: AI Chat Backend & LLM Integration

## /plan prompt

```
Implement with these technical decisions:

## Service (services/ai-chat/)
- gRPC server on port 50053 using grpcio with asyncio
- Conversation state: Redis hash "conv:{session_id}" with fields: user_id, language, criteria_state (JSON string), turn_count, created_at. TTL 24h (extended on each interaction).
- Message history: Redis list "conv:{session_id}:messages" with JSON-encoded messages. Max 40 messages (sliding window for long conversations).

## LLM Providers (services/ai-chat/providers/)
- base.py: BaseLLMProvider with async generate(messages: list[Message], system: str) → AsyncIterator[str]
- claude.py: anthropic AsyncAnthropic client, model="claude-sonnet-4-20250514", max_tokens=1000, streaming=True
- openai.py: openai AsyncOpenAI client, model="gpt-4o", stream=True
- litellm.py: litellm.acompletion with stream=True. Model from env var LITELLM_MODEL.
- Selection: env var LLM_PROVIDER = "claude" | "openai" | "litellm"
- Fallback: on provider error (timeout, rate limit) → try secondary provider (env FALLBACK_LLM_PROVIDER)

## Prompt (services/ai-chat/prompts/system_prompt.jinja2)
- Role: expert multilingual real estate advisor
- Instruction: respond in user's detected language, ask max 1 question per turn, follow progressive refinement flow
- Available data: injected as JSON block (countries, property_types, active_zones)
- Output format: always end response with ```json block containing {status, confidence, criteria, pending_dimensions, suggested_chips, show_visual_references}
- Market context: injected before user's message as [MARKET DATA] block

## Criteria Parser
- Regex extract ```json ... ``` block from LLM response
- Parse with json.loads, validate against CriteriaState Pydantic model
- If parse fails: retry LLM once with "Please include the JSON criteria block". If still fails: return text-only response with last known criteria state.

## Visual References
- PostgreSQL table visual_references (id, image_url, tags TEXT[], description)
- Query: SELECT * FROM visual_references WHERE tags @> ARRAY['modern', 'loft'] LIMIT 5
- Triggered when criteria parser detects show_visual_references in LLM output

## Finalization
- When criteria.status == "ready" and user confirms:
  1. Convert criteria JSON → listing search query params
  2. gRPC call to api-gateway listings search
  3. gRPC call to api-gateway create alert rule
  4. Return results + alert confirmation via streaming response
```
