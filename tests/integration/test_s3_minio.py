"""Teste de integracao opcional com MinIO real (RUN_S3_TESTS=1)."""

from __future__ import annotations

import os
from uuid import uuid4

import pytest

from modules.image_generation.adapters.s3_storage import S3ObjectStorage

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.environ.get("RUN_S3_TESTS") != "1",
        reason="RUN_S3_TESTS!=1; teste com MinIO real desativado",
    ),
]


@pytest.mark.asyncio
async def test_roundtrip_no_minio_real() -> None:
    storage = S3ObjectStorage(
        endpoint_url=os.environ["S3_ENDPOINT_URL"],
        bucket=os.environ["S3_BUCKET"],
        access_key=os.environ["S3_ACCESS_KEY"],
        secret_key=os.environ["S3_SECRET_KEY"],
        auto_create_bucket=True,
    )
    key = f"tests/{uuid4()}/result.png"
    await storage.put_object(key, b"png-test")
    assert await storage.get_object(key) == b"png-test"
    url = await storage.presigned_get_url(key)
    assert "X-Amz-Signature" in url
    await storage.delete_object(key)
