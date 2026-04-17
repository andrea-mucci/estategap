"""Async proxy-manager gRPC client wrapper."""

from __future__ import annotations

from dataclasses import dataclass

import grpc

from estategap.v1 import proxy_pb2, proxy_pb2_grpc


@dataclass(slots=True)
class ProxyAssignment:
    """Assigned proxy endpoint details."""

    proxy_url: str
    proxy_id: str


class ProxyClient:
    """Thin async wrapper around the proxy-manager gRPC API."""

    def __init__(self, address: str) -> None:
        self._address = address
        self._channel: grpc.aio.Channel | None = None
        self._stub: proxy_pb2_grpc.ProxyServiceStub | None = None

    async def get_proxy(self, country: str, portal: str, session_id: str) -> ProxyAssignment:
        """Request a proxy assignment for a country and portal."""

        request_kwargs = {
            "country_code": country.upper(),
            "portal_id": portal.lower(),
        }
        descriptor = proxy_pb2.GetProxyRequest.DESCRIPTOR
        if "session_id" in descriptor.fields_by_name:
            request_kwargs["session_id"] = session_id

        response = await self._get_stub().GetProxy(proxy_pb2.GetProxyRequest(**request_kwargs))
        return ProxyAssignment(proxy_url=response.proxy_url, proxy_id=response.proxy_id)

    async def report_result(
        self,
        proxy_id: str,
        success: bool,
        status_code: int,
        latency_ms: int,
    ) -> None:
        """Report the outcome of a request for proxy health tracking."""

        await self._get_stub().ReportResult(
            proxy_pb2.ReportResultRequest(
                proxy_id=proxy_id,
                success=success,
                status_code=status_code,
                latency_ms=latency_ms,
            ),
        )

    async def close(self) -> None:
        """Close the underlying gRPC channel."""

        if self._channel is not None:
            await self._channel.close()
            self._channel = None
            self._stub = None

    def _get_stub(self) -> proxy_pb2_grpc.ProxyServiceStub:
        if self._stub is None:
            self._channel = grpc.aio.insecure_channel(self._address)
            self._stub = proxy_pb2_grpc.ProxyServiceStub(self._channel)
        return self._stub
