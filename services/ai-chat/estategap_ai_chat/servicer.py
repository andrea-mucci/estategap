"""gRPC servicer for AI chat conversations."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import datetime
import json
from time import perf_counter
from typing import TYPE_CHECKING, Any
from uuid import uuid4

import grpc
from estategap.v1 import ai_chat_pb2, ai_chat_pb2_grpc, common_pb2
import structlog

from .finalization import CriteriaFinalizer
from .market_context import MarketContextClient
from .metrics import (
    AI_CHAT_CONVERSATIONS_TOTAL,
    AI_CHAT_CRITERIA_PARSE_ERRORS_TOTAL,
    AI_CHAT_FALLBACK_ACTIVATIONS_TOTAL,
    AI_CHAT_LLM_LATENCY_SECONDS,
    AI_CHAT_SUBSCRIPTION_REJECTIONS_TOTAL,
    AI_CHAT_TURNS_TOTAL,
)
from .parser import CriteriaState, ParseError, extract_criteria
from .prompts import PromptContext, render_system_prompt
from .providers import RETRYABLE_ERRORS
from .providers.base import BaseLLMProvider, LLMMessage
from .session import ConversationSession
from .subscription import (
    LimitExceededError,
    check_conversation_limit,
    check_turn_limit,
    register_conversation,
)
from .visual_refs import query_by_tags


logger = structlog.get_logger(__name__)
CONFIRMATION_KEYWORDS = {"yes", "ok", "okay", "confirm", "search", "go", "trova", "si", "sí"}
DEFAULT_PROPERTY_TYPES = ["apartment", "house", "villa", "studio", "commercial"]

if TYPE_CHECKING:
    AIChatServiceServicerBase = object
else:
    AIChatServiceServicerBase = ai_chat_pb2_grpc.AIChatServiceServicer


def _timestamp_from_iso(value: str | None) -> common_pb2.Timestamp:
    if not value:
        return common_pb2.Timestamp()
    try:
        moment = datetime.fromisoformat(value)
    except ValueError:
        return common_pb2.Timestamp()
    return common_pb2.Timestamp(millis=int(moment.timestamp() * 1000))


class AIChatServicer(AIChatServiceServicerBase):
    """Implements the AI chat RPCs."""

    def __init__(
        self,
        config: Any,
        db_pool: Any,
        redis_client: Any,
        llm_provider: BaseLLMProvider,
        fallback_provider: BaseLLMProvider,
        *,
        market_context_client: MarketContextClient | None = None,
        criteria_finalizer: Any | None = None,
        visual_reference_query: Any = query_by_tags,
    ) -> None:
        self.config = config
        self.db_pool = db_pool
        self.redis_client = redis_client
        self.llm_provider = llm_provider
        self.fallback_provider = fallback_provider
        self.market_context_client = market_context_client or MarketContextClient(config)
        self.criteria_finalizer = criteria_finalizer or CriteriaFinalizer()
        self.visual_reference_query = visual_reference_query

    async def Chat(
        self,
        request_iterator: AsyncIterator[ai_chat_pb2.ChatRequest],
        context: grpc.aio.ServicerContext[ai_chat_pb2.ChatRequest, ai_chat_pb2.ChatResponse],
    ) -> AsyncIterator[ai_chat_pb2.ChatResponse]:
        metadata = {item.key.lower(): item.value for item in context.invocation_metadata()}
        user_id = metadata.get("x-user-id")
        tier = metadata.get("x-subscription-tier", "free").lower()
        if not user_id:
            await context.abort(grpc.StatusCode.UNAUTHENTICATED, "missing x-user-id metadata")
        user_id_str = str(user_id)

        session_store = ConversationSession(self.redis_client)
        active_conversation_id: str | None = None

        async for request in request_iterator:
            conversation_id = request.conversation_id or active_conversation_id or str(uuid4())
            active_conversation_id = conversation_id
            is_new_session = not await session_store.exists(conversation_id)

            if not is_new_session and request.conversation_id and request.conversation_id != conversation_id:
                await context.abort(grpc.StatusCode.NOT_FOUND, "conversation not found")
            if request.conversation_id and not await session_store.exists(request.conversation_id):
                await context.abort(grpc.StatusCode.NOT_FOUND, "conversation not found")

            session_data = await session_store.get(conversation_id) if not is_new_session else {}
            turn_count = int(session_data.get("turn_count", "0"))
            language = session_data.get("language") or self._detect_language(request.country_code)

            try:
                if is_new_session:
                    await check_conversation_limit(
                        user_id=user_id_str,
                        tier=tier,
                        redis_client=self.redis_client,
                        session_id=conversation_id,
                        record=False,
                    )
                check_turn_limit(turn_count, tier)
            except LimitExceededError as exc:
                AI_CHAT_SUBSCRIPTION_REJECTIONS_TOTAL.inc()
                await context.abort(grpc.StatusCode.RESOURCE_EXHAUSTED, str(exc))

            stored_messages = await session_store.get_messages(conversation_id) if not is_new_session else []
            prompt_context = PromptContext(
                language=language,
                countries=[request.country_code.upper()] if request.country_code else [],
                property_types=DEFAULT_PROPERTY_TYPES,
                active_zones=self._extract_active_zones(session_data),
                market_data=await self._fetch_market_context(session_data),
            )
            system_prompt = render_system_prompt(prompt_context)
            llm_messages = [*stored_messages, LLMMessage(role="user", content=request.user_message)]

            provider_name, assistant_text, streamed_tokens = await self._collect_assistant_response(
                context=context,
                llm_messages=llm_messages,
                system_prompt=system_prompt,
            )
            for token in streamed_tokens:
                yield ai_chat_pb2.ChatResponse(
                    conversation_id=conversation_id,
                    chunk=token,
                    is_final=False,
                )

            criteria_state = await self._parse_or_retry(llm_messages, system_prompt, assistant_text)
            visual_payload = await self._build_visual_reference_payload(criteria_state)
            listing_ids: list[str] = []
            alert_rule_id = ""
            if criteria_state is not None and criteria_state.status == "ready" and self._is_confirmation(
                request.user_message
            ):
                listing_ids, alert_rule_id = await self.criteria_finalizer.finalize(
                    conversation_id,
                    criteria_state.criteria,
                )

            if is_new_session:
                await session_store.create(
                    session_id=conversation_id,
                    user_id=user_id_str,
                    language=language,
                    tier=tier,
                )
                await register_conversation(
                    user_id=user_id_str,
                    tier=tier,
                    redis_client=self.redis_client,
                    session_id=conversation_id,
                )
                AI_CHAT_CONVERSATIONS_TOTAL.labels(tier=tier).inc()

            await session_store.append_message(conversation_id, "user", request.user_message)
            await session_store.append_message(conversation_id, "assistant", assistant_text)
            if criteria_state is not None:
                await session_store.update_criteria(
                    conversation_id,
                    criteria_state.model_dump(mode="json"),
                )
            await session_store.increment_turn(conversation_id)
            AI_CHAT_TURNS_TOTAL.labels(provider=provider_name).inc()

            if visual_payload is not None:
                yield ai_chat_pb2.ChatResponse(
                    conversation_id=conversation_id,
                    chunk=visual_payload,
                    is_final=False,
                )
            if listing_ids or alert_rule_id:
                yield ai_chat_pb2.ChatResponse(
                    conversation_id=conversation_id,
                    chunk=self._json_chunk(
                        {
                            "listing_ids": listing_ids,
                            "alert_rule_id": alert_rule_id,
                        }
                    ),
                    is_final=False,
                )
            yield ai_chat_pb2.ChatResponse(
                conversation_id=conversation_id,
                chunk="",
                is_final=True,
                listing_ids=listing_ids,
            )

    async def GetConversation(
        self,
        request: ai_chat_pb2.GetConversationRequest,
        context: grpc.aio.ServicerContext[
            ai_chat_pb2.GetConversationRequest,
            ai_chat_pb2.GetConversationResponse,
        ],
    ) -> ai_chat_pb2.GetConversationResponse:
        session_store = ConversationSession(self.redis_client)
        if not await session_store.exists(request.conversation_id):
            await context.abort(grpc.StatusCode.NOT_FOUND, "conversation not found")
        session_data = await session_store.get(request.conversation_id)
        messages = await session_store.get_messages(request.conversation_id)
        turns = [
            ai_chat_pb2.ConversationTurn(
                role=message.role,
                content=message.content,
                timestamp=_timestamp_from_iso(session_data.get("last_active_at")),
            )
            for message in messages
        ]
        return ai_chat_pb2.GetConversationResponse(
            conversation_id=request.conversation_id,
            turns=turns,
            created_at=_timestamp_from_iso(session_data.get("created_at")),
        )

    async def ListConversations(
        self,
        request: ai_chat_pb2.ListConversationsRequest,
        context: grpc.aio.ServicerContext[
            ai_chat_pb2.ListConversationsRequest,
            ai_chat_pb2.ListConversationsResponse,
        ],
    ) -> ai_chat_pb2.ListConversationsResponse:
        del context
        page = max(request.pagination.page, 1) if request.HasField("pagination") else 1
        page_size = max(request.pagination.page_size, 1) if request.HasField("pagination") else 20
        sessions: list[dict[str, str]] = []

        async for key in self.redis_client.scan_iter(match="conv:*"):
            session_key = key.decode("utf-8") if isinstance(key, bytes) else str(key)
            if session_key.endswith(":messages"):
                continue
            session_id = session_key.removeprefix("conv:")
            session_store = ConversationSession(self.redis_client)
            data = await session_store.get(session_id)
            if data.get("user_id") != request.user_id:
                continue
            data["conversation_id"] = session_id
            sessions.append(data)

        sessions.sort(key=lambda item: item.get("last_active_at", ""), reverse=True)
        total_count = len(sessions)
        start = (page - 1) * page_size
        end = start + page_size
        page_sessions = sessions[start:end]

        return ai_chat_pb2.ListConversationsResponse(
            conversations=[
                ai_chat_pb2.ConversationSummary(
                    conversation_id=item["conversation_id"],
                    preview=item.get("preview", ""),
                    created_at=_timestamp_from_iso(item.get("created_at")),
                )
                for item in page_sessions
            ],
            pagination=common_pb2.PaginationResponse(
                total_count=total_count,
                page=page,
                page_size=page_size,
                has_next=end < total_count,
            ),
        )

    async def _collect_assistant_response(
        self,
        *,
        context: grpc.aio.ServicerContext[ai_chat_pb2.ChatRequest, ai_chat_pb2.ChatResponse],
        llm_messages: list[LLMMessage],
        system_prompt: str,
    ) -> tuple[str, str, list[str]]:
        provider = self.llm_provider
        for attempt in range(2):
            started = perf_counter()
            first_token_seen = False
            chunks: list[str] = []
            try:
                async for token in provider.generate(llm_messages, system_prompt):
                    chunks.append(token)
                    if not first_token_seen:
                        AI_CHAT_LLM_LATENCY_SECONDS.labels(provider=provider.name).observe(
                            perf_counter() - started
                        )
                        first_token_seen = True
                return provider.name, "".join(chunks), chunks
            except RETRYABLE_ERRORS as exc:
                if attempt == 1:
                    logger.exception("llm_provider_unavailable", provider=provider.name, error=str(exc))
                    await context.abort(grpc.StatusCode.INTERNAL, "LLM unavailable")
                AI_CHAT_FALLBACK_ACTIVATIONS_TOTAL.inc()
                provider = self.fallback_provider
        return provider.name, "", []

    async def _parse_or_retry(
        self,
        llm_messages: list[LLMMessage],
        system_prompt: str,
        assistant_text: str,
    ) -> CriteriaState | None:
        try:
            return extract_criteria(assistant_text)
        except ParseError:
            AI_CHAT_CRITERIA_PARSE_ERRORS_TOTAL.inc()

        repair_messages = [
            *llm_messages,
            LLMMessage(role="assistant", content=assistant_text),
            LLMMessage(
                role="system",
                content="Repeat only a valid response that ends with the required JSON block.",
            ),
        ]
        retry_chunks: list[str] = []
        try:
            async for token in self.fallback_provider.generate(repair_messages, system_prompt):
                retry_chunks.append(token)
        except Exception:  # noqa: BLE001
            return None
        if not retry_chunks:
            return None
        try:
            return extract_criteria("".join(retry_chunks))
        except ParseError:
            AI_CHAT_CRITERIA_PARSE_ERRORS_TOTAL.inc()
            return None

    async def _fetch_market_context(self, session_data: dict[str, str]) -> dict[str, Any] | None:
        zone_ids = self._extract_zone_ids(session_data)
        market_data = await self.market_context_client.fetch(zone_ids)
        return market_data.model_dump(mode="json") if market_data is not None else None

    def _extract_zone_ids(self, session_data: dict[str, str]) -> list[str]:
        raw_criteria = session_data.get("criteria_state")
        if not raw_criteria:
            return []
        try:
            payload = json.loads(raw_criteria)
        except json.JSONDecodeError:
            return []
        location = payload.get("criteria", {}).get("location")
        if isinstance(location, dict):
            zone_id = location.get("zone_id")
            return [str(zone_id)] if zone_id else []
        if isinstance(location, list):
            return [str(item) for item in location if item]
        if isinstance(location, str) and location:
            return [location]
        return []

    def _extract_active_zones(self, session_data: dict[str, str]) -> list[dict[str, Any]]:
        zone_ids = self._extract_zone_ids(session_data)
        return [{"id": zone_id, "name": zone_id, "country": ""} for zone_id in zone_ids]

    async def _build_visual_reference_payload(
        self,
        criteria_state: CriteriaState | None,
    ) -> str | None:
        if criteria_state is None or not criteria_state.show_visual_references:
            return None
        tags = self._extract_visual_tags(criteria_state.criteria)
        visual_refs = await self.visual_reference_query(tags, self.db_pool)
        if not visual_refs:
            return None
        return self._json_chunk([visual_ref.model_dump(mode="json") for visual_ref in visual_refs])

    def _extract_visual_tags(self, criteria: dict[str, Any]) -> list[str]:
        candidates: list[str] = []
        for key in ("style", "amenities", "extras"):
            value = criteria.get(key)
            if isinstance(value, str):
                candidates.extend(part.strip().lower() for part in value.replace("/", ",").split(","))
            elif isinstance(value, list):
                candidates.extend(str(item).strip().lower() for item in value)
        return [candidate for candidate in candidates if candidate]

    def _detect_language(self, country_code: str) -> str:
        mapping = {
            "ES": "es",
            "FR": "fr",
            "IT": "it",
            "PT": "pt",
            "DE": "de",
        }
        return mapping.get(country_code.upper(), "en") if country_code else "en"

    def _is_confirmation(self, text: str) -> bool:
        lowered = text.casefold()
        return any(keyword in lowered for keyword in CONFIRMATION_KEYWORDS)

    def _json_chunk(self, payload: Any) -> str:
        return "```json\n" + json.dumps(payload, ensure_ascii=True) + "\n```"
