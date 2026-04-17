"""Shared sync and async S3 client wrappers."""

from __future__ import annotations

import asyncio
from io import BufferedReader, BytesIO
from typing import IO, Any

import boto3
from botocore.config import Config as BotoConfig
from botocore.exceptions import BotoCoreError, ClientError

from .config import S3Config, S3Error, S3HealthCheckError

MAX_PRESIGN_EXPIRY_SECONDS = 7 * 24 * 60 * 60


def _client_kwargs(config: S3Config) -> dict[str, Any]:
    return {
        "endpoint_url": config.s3_endpoint,
        "region_name": config.s3_region,
        "aws_access_key_id": config.s3_access_key_id,
        "aws_secret_access_key": config.s3_secret_access_key,
        "config": BotoConfig(s3={"addressing_style": "path"}),
    }


def _read_body(body: bytes | IO[bytes]) -> tuple[IO[bytes], int]:
    if isinstance(body, bytes):
        return BytesIO(body), len(body)
    if isinstance(body, BufferedReader):
        current = body.tell()
        data = body.read()
        body.seek(current)
        return BytesIO(data), len(data)
    data = body.read()
    if hasattr(body, "seek"):
        body.seek(0)
    return BytesIO(data), len(data)


class SyncS3Client:
    """Thin synchronous S3 client wrapper."""

    def __init__(self, config: S3Config) -> None:
        self._config = config
        self._client = boto3.client("s3", **_client_kwargs(config))

    def bucket_name(self, logical: str) -> str:
        return f"{self._config.s3_bucket_prefix}-{logical}"

    def put_object(
        self,
        bucket: str,
        key: str,
        body: bytes | IO[bytes],
        content_type: str = "application/octet-stream",
    ) -> None:
        payload, content_length = _read_body(body)
        try:
            self._client.put_object(
                Bucket=bucket,
                Key=key,
                Body=payload,
                ContentType=content_type,
                ContentLength=content_length,
            )
        except (BotoCoreError, ClientError) as exc:
            raise S3Error(str(exc)) from exc

    def get_object(self, bucket: str, key: str) -> bytes:
        try:
            response = self._client.get_object(Bucket=bucket, Key=key)
        except (BotoCoreError, ClientError) as exc:
            raise S3Error(str(exc)) from exc
        return response["Body"].read()

    def delete_object(self, bucket: str, key: str) -> None:
        try:
            self._client.delete_object(Bucket=bucket, Key=key)
        except (BotoCoreError, ClientError) as exc:
            raise S3Error(str(exc)) from exc

    def list_objects(self, bucket: str, prefix: str = "") -> list[str]:
        paginator = self._client.get_paginator("list_objects_v2")
        keys: list[str] = []
        try:
            for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
                for item in page.get("Contents", []):
                    key = item.get("Key")
                    if isinstance(key, str):
                        keys.append(key)
        except (BotoCoreError, ClientError) as exc:
            raise S3Error(str(exc)) from exc
        return keys

    def presign_get_object(self, bucket: str, key: str, expiry_seconds: int = 3600) -> str:
        if expiry_seconds <= 0 or expiry_seconds > MAX_PRESIGN_EXPIRY_SECONDS:
            msg = f"invalid presign expiry {expiry_seconds}"
            raise S3Error(msg)
        try:
            return str(
                self._client.generate_presigned_url(
                    "get_object",
                    Params={"Bucket": bucket, "Key": key},
                    ExpiresIn=expiry_seconds,
                )
            )
        except (BotoCoreError, ClientError) as exc:
            raise S3Error(str(exc)) from exc

    def health_check(self, required_buckets: list[str]) -> None:
        missing: list[str] = []
        for bucket in required_buckets:
            try:
                self._client.head_bucket(Bucket=bucket)
            except (BotoCoreError, ClientError):
                missing.append(bucket)
        if missing:
            raise S3HealthCheckError(missing)


class S3Client:
    """Async S3 client wrapper using aiobotocore when available."""

    def __init__(self, config: S3Config) -> None:
        self._config = config
        self._sync = SyncS3Client(config)
        self._session: Any | None = None
        self._client: Any | None = None

    async def __aenter__(self) -> "S3Client":
        try:
            from aiobotocore.session import get_session
        except ModuleNotFoundError:
            return self

        self._session = get_session()
        self._client = await self._session.create_client("s3", **_client_kwargs(self._config)).__aenter__()
        return self

    async def __aexit__(self, *args: object) -> None:
        if self._client is not None:
            await self._client.__aexit__(*args)
            self._client = None
            self._session = None

    def bucket_name(self, logical: str) -> str:
        return self._sync.bucket_name(logical)

    async def put_object(
        self,
        bucket: str,
        key: str,
        body: bytes | IO[bytes],
        content_type: str = "application/octet-stream",
    ) -> None:
        if self._client is None:
            await asyncio.to_thread(self._sync.put_object, bucket, key, body, content_type)
            return
        payload, content_length = _read_body(body)
        try:
            await self._client.put_object(
                Bucket=bucket,
                Key=key,
                Body=payload.read(),
                ContentType=content_type,
                ContentLength=content_length,
            )
        except (BotoCoreError, ClientError) as exc:
            raise S3Error(str(exc)) from exc

    async def get_object(self, bucket: str, key: str) -> bytes:
        if self._client is None:
            return await asyncio.to_thread(self._sync.get_object, bucket, key)
        try:
            response = await self._client.get_object(Bucket=bucket, Key=key)
            body = response["Body"]
            return await body.read()
        except (BotoCoreError, ClientError) as exc:
            raise S3Error(str(exc)) from exc

    async def delete_object(self, bucket: str, key: str) -> None:
        if self._client is None:
            await asyncio.to_thread(self._sync.delete_object, bucket, key)
            return
        try:
            await self._client.delete_object(Bucket=bucket, Key=key)
        except (BotoCoreError, ClientError) as exc:
            raise S3Error(str(exc)) from exc

    async def list_objects(self, bucket: str, prefix: str = "") -> list[str]:
        if self._client is None:
            return await asyncio.to_thread(self._sync.list_objects, bucket, prefix)
        paginator = self._client.get_paginator("list_objects_v2")
        keys: list[str] = []
        try:
            async for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
                for item in page.get("Contents", []):
                    key = item.get("Key")
                    if isinstance(key, str):
                        keys.append(key)
        except (BotoCoreError, ClientError) as exc:
            raise S3Error(str(exc)) from exc
        return keys

    async def presign_get_object(self, bucket: str, key: str, expiry_seconds: int = 3600) -> str:
        return await asyncio.to_thread(self._sync.presign_get_object, bucket, key, expiry_seconds)

    async def health_check(self, required_buckets: list[str]) -> None:
        if self._client is None:
            await asyncio.to_thread(self._sync.health_check, required_buckets)
            return
        missing: list[str] = []
        for bucket in required_buckets:
            try:
                await self._client.head_bucket(Bucket=bucket)
            except (BotoCoreError, ClientError):
                missing.append(bucket)
        if missing:
            raise S3HealthCheckError(missing)


__all__ = ["MAX_PRESIGN_EXPIRY_SECONDS", "S3Client", "SyncS3Client"]
