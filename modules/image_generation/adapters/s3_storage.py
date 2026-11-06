"""Adapter S3 compativel com MinIO, executado em thread (nao bloqueia o loop)."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

from modules.image_generation.application.ports.object_storage import ObjectStoragePort

logger = logging.getLogger(__name__)


class S3ObjectStorage(ObjectStoragePort):
    def __init__(
        self,
        *,
        endpoint_url: str,
        bucket: str,
        access_key: str,
        secret_key: str,
        region: str = "us-east-1",
        presign_expires_seconds: int = 900,
        auto_create_bucket: bool = False,
        public_endpoint_url: str = "",
        client_factory: Callable[[], Any] | None = None,
    ) -> None:
        self._endpoint_url = endpoint_url
        self._public_endpoint_url = public_endpoint_url or endpoint_url
        self._bucket = bucket
        self._access_key = access_key
        self._secret_key = secret_key
        self._region = region
        self._presign_expires = presign_expires_seconds
        self._auto_create_bucket = auto_create_bucket
        self._client_factory = client_factory
        self._client: Any | None = None
        self._presign_client: Any | None = None
        self._bucket_ready = False

    @property
    def bucket(self) -> str:
        return self._bucket

    def _get_client(self) -> Any:
        if self._client is None:
            self._client = self._build_client(self._endpoint_url)
        return self._client

    def _get_presign_client(self) -> Any:
        if self._presign_client is None:
            if self._public_endpoint_url == self._endpoint_url:
                self._presign_client = self._get_client()
            else:
                self._presign_client = self._build_client(self._public_endpoint_url)
        return self._presign_client

    def _build_client(self, endpoint_url: str) -> Any:
        if self._client_factory is not None:
            return self._client_factory()
        import boto3
        from botocore.config import Config

        return boto3.client(
            "s3",
            endpoint_url=endpoint_url or None,
            aws_access_key_id=self._access_key,
            aws_secret_access_key=self._secret_key,
            region_name=self._region,
            config=Config(signature_version="s3v4"),
        )

    async def put_object(
        self, key: str, data: bytes, *, content_type: str = "image/png"
    ) -> None:
        await asyncio.to_thread(self._put_sync, key, data, content_type)

    def _put_sync(self, key: str, data: bytes, content_type: str) -> None:
        if self._auto_create_bucket and not self._bucket_ready:
            self._ensure_bucket_sync()
        self._get_client().put_object(
            Bucket=self._bucket, Key=key, Body=data, ContentType=content_type
        )

    async def get_object(self, key: str) -> bytes:
        return await asyncio.to_thread(self._get_sync, key)

    def _get_sync(self, key: str) -> bytes:
        response = self._get_client().get_object(Bucket=self._bucket, Key=key)
        return bytes(response["Body"].read())

    async def presigned_get_url(
        self, key: str, *, expires_seconds: int | None = None
    ) -> str:
        return await asyncio.to_thread(self._presign_sync, key, expires_seconds)

    def _presign_sync(self, key: str, expires_seconds: int | None) -> str:
        return str(
            self._get_presign_client().generate_presigned_url(
                "get_object",
                Params={"Bucket": self._bucket, "Key": key},
                ExpiresIn=expires_seconds or self._presign_expires,
            )
        )

    async def delete_object(self, key: str) -> None:
        await asyncio.to_thread(self._delete_sync, key)

    def _delete_sync(self, key: str) -> None:
        self._get_client().delete_object(Bucket=self._bucket, Key=key)

    async def ensure_bucket(self) -> None:
        await asyncio.to_thread(self._ensure_bucket_sync)

    def _ensure_bucket_sync(self) -> None:
        client = self._get_client()
        try:
            client.head_bucket(Bucket=self._bucket)
            self._bucket_ready = True
            return
        except Exception as exc:  # botocore ClientError (lazy import)
            if not self._auto_create_bucket:
                logger.warning("s3_bucket_unavailable", extra={"bucket": self._bucket})
                raise
            if not _is_not_found(exc):
                raise
        client.create_bucket(Bucket=self._bucket)
        self._bucket_ready = True

    async def delete_objects_older_than(self, prefix: str, *, hours: int) -> int:
        return await asyncio.to_thread(self._delete_older_than_sync, prefix, hours)

    def _delete_older_than_sync(self, prefix: str, hours: int) -> int:
        client = self._get_client()
        cutoff = datetime.now(UTC) - timedelta(hours=hours)
        deleted = 0
        continuation: str | None = None
        while True:
            kwargs: dict[str, Any] = {"Bucket": self._bucket, "Prefix": prefix}
            if continuation:
                kwargs["ContinuationToken"] = continuation
            response = client.list_objects_v2(**kwargs)
            stale = [
                {"Key": item["Key"]}
                for item in response.get("Contents", [])
                if item.get("LastModified") is not None
                and item["LastModified"] < cutoff
            ]
            if stale:
                client.delete_objects(
                    Bucket=self._bucket, Delete={"Objects": stale, "Quiet": True}
                )
                deleted += len(stale)
            if not response.get("IsTruncated"):
                break
            continuation = response.get("NextContinuationToken")
        return deleted


def _is_not_found(exc: Exception) -> bool:
    response = getattr(exc, "response", None)
    if not isinstance(response, dict):
        return False
    code = str(response.get("Error", {}).get("Code", ""))
    return code in {"404", "NoSuchBucket", "NotFound"}
