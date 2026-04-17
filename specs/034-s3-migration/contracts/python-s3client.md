# Contract: Python Async S3 Client (`libs/common/s3client`)

**Branch**: `034-s3-migration` | **Date**: 2026-04-17

## Module

```python
# libs/common/estategap_common/s3client/__init__.py
from estategap_common.s3client.client import S3Client, S3Config
```

## Configuration

```python
from pydantic_settings import BaseSettings
from pydantic import Field

class S3Config(BaseSettings):
    s3_endpoint: str          = Field(alias="S3_ENDPOINT")
    s3_region: str            = Field(default="fsn1", alias="S3_REGION")
    s3_access_key_id: str     = Field(alias="S3_ACCESS_KEY_ID")
    s3_secret_access_key: str = Field(alias="S3_SECRET_ACCESS_KEY")
    s3_bucket_prefix: str     = Field(alias="S3_BUCKET_PREFIX")

    model_config = SettingsConfigDict(populate_by_name=True)
```

## Class Interface

```python
class S3Client:
    """Async S3 client wrapping aiobotocore for use in asyncio services."""

    def __init__(self, config: S3Config) -> None: ...

    def bucket_name(self, logical: str) -> str:
        """Returns f"{config.s3_bucket_prefix}-{logical}"."""
        ...

    async def put_object(
        self,
        bucket: str,
        key: str,
        body: bytes | IO[bytes],
        content_type: str = "application/octet-stream",
    ) -> None:
        """Upload body to bucket/key. Raises S3Error on failure."""
        ...

    async def get_object(self, bucket: str, key: str) -> bytes:
        """Download and return full object body. Raises S3Error if not found."""
        ...

    async def delete_object(self, bucket: str, key: str) -> None:
        """Delete object. Idempotent — no error if key does not exist."""
        ...

    async def list_objects(self, bucket: str, prefix: str = "") -> list[str]:
        """Return list of keys matching prefix. Handles pagination internally."""
        ...

    async def presign_get_object(
        self,
        bucket: str,
        key: str,
        expiry_seconds: int = 3600,
    ) -> str:
        """Return pre-signed GET URL valid for expiry_seconds (max 604800 = 7 days)."""
        ...

    async def health_check(self, required_buckets: list[str]) -> None:
        """
        Call head_bucket for every bucket. Collect all failures.
        Raises S3HealthCheckError listing every missing bucket if any fail.
        """
        ...

    async def __aenter__(self) -> "S3Client": ...
    async def __aexit__(self, *args: object) -> None: ...
```

## Exceptions

```python
class S3Error(Exception):
    """Base exception for all S3 client errors."""

class S3HealthCheckError(S3Error):
    """Raised by health_check() when one or more buckets are inaccessible."""
    missing_buckets: list[str]
    # str: "S3 health check failed: missing buckets: ['estategap-ml-models']"
```

## Sync Wrapper (for non-async callers)

```python
class SyncS3Client:
    """
    Thin synchronous wrapper for services that are not async
    (e.g., Alembic scripts, CLI tools).
    Uses boto3 directly instead of aiobotocore.
    """
    def __init__(self, config: S3Config) -> None: ...
    def bucket_name(self, logical: str) -> str: ...
    def put_object(self, bucket: str, key: str, body: bytes, content_type: str = "application/octet-stream") -> None: ...
    def get_object(self, bucket: str, key: str) -> bytes: ...
    def delete_object(self, bucket: str, key: str) -> None: ...
    def list_objects(self, bucket: str, prefix: str = "") -> list[str]: ...
    def presign_get_object(self, bucket: str, key: str, expiry_seconds: int = 3600) -> str: ...
    def health_check(self, required_buckets: list[str]) -> None: ...
```

## Test Fixtures (`libs/common/estategap_common/testing/fixtures.py`)

```python
import pytest
from moto import mock_aws

@pytest.fixture
def s3_config() -> S3Config:
    """Returns a test S3Config pointing to moto's in-process S3 mock."""
    return S3Config(
        s3_endpoint="https://s3.amazonaws.com",  # moto intercepts this
        s3_region="us-east-1",
        s3_access_key_id="test",
        s3_secret_access_key="test",
        s3_bucket_prefix="test",
    )

@pytest.fixture
def s3_client(s3_config: S3Config):
    """Yields an S3Client backed by moto. All buckets are empty."""
    with mock_aws():
        yield SyncS3Client(s3_config)

@pytest.fixture
async def async_s3_client(s3_config: S3Config):
    """Async variant for pytest-asyncio tests."""
    with mock_aws():
        async with S3Client(s3_config) as client:
            yield client
```

## Usage Example

```python
from estategap_common.s3client import S3Client, S3Config, S3HealthCheckError

config = S3Config()  # reads S3_* from environment

async def main() -> None:
    async with S3Client(config) as s3:
        # Startup check
        try:
            await s3.health_check([
                s3.bucket_name("ml-models"),
                s3.bucket_name("training-data"),
            ])
        except S3HealthCheckError as e:
            logger.error("S3 health check failed", missing=e.missing_buckets)
            raise SystemExit(1)

        # Upload artifact
        await s3.put_object(
            s3.bucket_name("ml-models"),
            "fr/v42/model.onnx",
            model_bytes,
            content_type="application/octet-stream",
        )

        # Get presigned URL
        url = await s3.presign_get_object(
            s3.bucket_name("listing-photos"),
            "fr/abc123/0.jpg",
            expiry_seconds=3600,
        )
```
