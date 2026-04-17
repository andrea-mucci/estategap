from __future__ import annotations

import pytest
from moto import mock_aws

from estategap_common.s3client import S3Client, S3Config, S3HealthCheckError, SyncS3Client


@pytest.fixture
def s3_config() -> S3Config:
    return S3Config(
        s3_endpoint="https://s3.amazonaws.com",
        s3_region="us-east-1",
        s3_access_key_id="test",
        s3_secret_access_key="test",
        s3_bucket_prefix="test",
    )


@pytest.fixture
def s3_client(s3_config: S3Config) -> SyncS3Client:
    with mock_aws():
        yield SyncS3Client(s3_config)


@pytest.fixture
async def async_s3_client(s3_config: S3Config) -> S3Client:
    with mock_aws():
        async with S3Client(s3_config) as client:
            yield client


def test_sync_s3_client_round_trip_and_presign(s3_client: SyncS3Client) -> None:
    s3_client._client.create_bucket(Bucket=s3_client.bucket_name("ml-models"))
    s3_client.put_object(s3_client.bucket_name("ml-models"), "models/model.onnx", b"payload")

    payload = s3_client.get_object(s3_client.bucket_name("ml-models"), "models/model.onnx")
    url = s3_client.presign_get_object(s3_client.bucket_name("ml-models"), "models/model.onnx")

    assert payload == b"payload"
    assert url


def test_sync_s3_client_health_check_reports_all_missing_buckets(s3_client: SyncS3Client) -> None:
    s3_client._client.create_bucket(Bucket=s3_client.bucket_name("ml-models"))

    with pytest.raises(S3HealthCheckError) as exc_info:
        s3_client.health_check([
            s3_client.bucket_name("ml-models"),
            s3_client.bucket_name("training-data"),
            s3_client.bucket_name("exports"),
        ])

    assert exc_info.value.missing_buckets == [
        s3_client.bucket_name("training-data"),
        s3_client.bucket_name("exports"),
    ]


@pytest.mark.asyncio
async def test_async_s3_client_round_trip_and_health(async_s3_client: S3Client) -> None:
    client = async_s3_client
    client._sync._client.create_bucket(Bucket=client.bucket_name("ml-models"))

    await client.put_object(client.bucket_name("ml-models"), "models/model.onnx", b"payload")
    payload = await client.get_object(client.bucket_name("ml-models"), "models/model.onnx")

    assert payload == b"payload"
    await client.health_check([client.bucket_name("ml-models")])
