"""AI chat gRPC server lifecycle."""

from __future__ import annotations

from typing import Any

import grpc

from estategap.v1 import ai_chat_pb2_grpc

from .metrics import start_metrics_server


async def serve(
    config: Any,
    db_pool: Any,
    redis_client: Any,
    llm_provider: Any,
    fallback_provider: Any,
) -> None:
    """Run the AI chat gRPC server."""

    from .servicer import AIChatServicer

    server = grpc.aio.server()
    ai_chat_pb2_grpc.add_AIChatServiceServicer_to_server(
        AIChatServicer(
            config=config,
            db_pool=db_pool,
            redis_client=redis_client,
            llm_provider=llm_provider,
            fallback_provider=fallback_provider,
        ),
        server,
    )
    server.add_insecure_port(f"[::]:{config.grpc_port}")
    start_metrics_server(config.metrics_port)
    await server.start()
    try:
        await server.wait_for_termination()
    finally:
        await server.stop(grace=5)


__all__ = ["serve"]
