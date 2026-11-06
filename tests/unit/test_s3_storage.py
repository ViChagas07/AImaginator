"""Testes do adapter S3 com cliente boto3 falso (sem MinIO real)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from modules.image_generation.adapters.s3_storage import S3ObjectStorage


class _FakeBody:
    def __init__(self, data: bytes) -> None:
        self._data = data

    def read(self) -> bytes:
        return self._data


class _FakeS3Client:
    def __init__(self, *, bucket_exists: bool = True) -> None:
        self.bucket_exists = bucket_exists
        self.created: list[str] = []
        self.puts: list[dict] = []
        self.deleted: list[dict] = []
        self.objects: dict[str, bytes] = {}
        self.list_response: dict = {"Contents": []}

    def head_bucket(self, *, Bucket: str) -> None:
        if not self.bucket_exists:
            error = Exception("not found")
            error.response = {"Error": {"Code": "404"}}  # type: ignore[attr-defined]
            raise error

    def create_bucket(self, *, Bucket: str) -> None:
        self.created.append(Bucket)
        self.bucket_exists = True

    def put_object(self, **kwargs) -> None:
        self.puts.append(kwargs)
        self.objects[kwargs["Key"]] = kwargs["Body"]

    def get_object(self, *, Bucket: str, Key: str):
        return {"Body": _FakeBody(self.objects[Key])}

    def generate_presigned_url(self, operation, Params, ExpiresIn):
        return f"https://minio.test/{Params['Bucket']}/{Params['Key']}?expires={ExpiresIn}"

    def delete_object(self, *, Bucket: str, Key: str) -> None:
        self.objects.pop(Key, None)

    def list_objects_v2(self, **kwargs):
        return self.list_response

    def delete_objects(self, *, Bucket: str, Delete: dict) -> None:
        self.deleted.append(Delete)
        for item in Delete["Objects"]:
            self.objects.pop(item["Key"], None)


def _storage(client: _FakeS3Client, *, auto_create: bool = False) -> S3ObjectStorage:
    return S3ObjectStorage(
        endpoint_url="http://localhost:9002",
        bucket="aimaginator-dev",
        access_key="aimaginator",
        secret_key="dev-secret",
        presign_expires_seconds=900,
        auto_create_bucket=auto_create,
        client_factory=lambda: client,
    )


@pytest.mark.unit
async def test_put_get_e_presign() -> None:
    client = _FakeS3Client()
    storage = _storage(client)

    await storage.put_object("generations/1/result.png", b"png-bytes")
    assert await storage.get_object("generations/1/result.png") == b"png-bytes"
    url = await storage.presigned_get_url("generations/1/result.png")
    assert url.startswith("https://minio.test/aimaginator-dev/")
    assert "expires=900" in url
    assert client.puts[0]["ContentType"] == "image/png"


@pytest.mark.unit
async def test_bucket_e_criado_em_desenvolvimento() -> None:
    client = _FakeS3Client(bucket_exists=False)
    storage = _storage(client, auto_create=True)

    await storage.put_object("sources/1/source.png", b"img")

    assert client.created == ["aimaginator-dev"]


@pytest.mark.unit
async def test_bucket_ausente_falha_sem_auto_create() -> None:
    client = _FakeS3Client(bucket_exists=False)
    storage = _storage(client, auto_create=False)

    with pytest.raises(Exception):
        await storage.ensure_bucket()


@pytest.mark.unit
async def test_delete_e_retencao_por_prefixo() -> None:
    client = _FakeS3Client()
    client.objects = {
        "sources/old/source.png": b"old",
        "sources/new/source.png": b"new",
    }
    old = datetime.now(UTC) - timedelta(hours=48)
    new = datetime.now(UTC) - timedelta(hours=1)
    client.list_response = {
        "Contents": [
            {"Key": "sources/old/source.png", "LastModified": old},
            {"Key": "sources/new/source.png", "LastModified": new},
        ],
        "IsTruncated": False,
    }
    storage = _storage(client)

    deleted = await storage.delete_objects_older_than("sources/", hours=24)

    assert deleted == 1
    assert "sources/old/source.png" not in client.objects
    assert "sources/new/source.png" in client.objects

    await storage.delete_object("sources/new/source.png")
    assert "sources/new/source.png" not in client.objects
