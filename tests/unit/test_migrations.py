"""Migrations da fase sao aditivas e com downgrade funcional (inspecao)."""

from __future__ import annotations

from pathlib import Path

import pytest

VERSIONS = Path("alembic/versions")


@pytest.mark.unit
def test_migrations_tem_downgrade_para_cada_alteracao() -> None:
    files = [
        VERSIONS / "20261106_120000_generation_object_keys.py",
        VERSIONS / "20261106_130000_assistant_moderation.py",
        VERSIONS / "20261106_140000_studio_features.py",
        VERSIONS / "20261106_150000_image_privacy.py",
    ]
    for path in files:
        text = path.read_text(encoding="utf-8")
        assert "def upgrade()" in text
        assert "def downgrade()" in text
        assert "drop_column" in text or "drop_table" in text or "drop_index" in text
        assert "DROP TABLE users" not in text
        assert "DROP TABLE generations" not in text


@pytest.mark.unit
def test_original_object_key_tem_migration_aditiva() -> None:
    text = (VERSIONS / "20261106_150000_image_privacy.py").read_text(encoding="utf-8")
    assert 'sa.Column("original_object_key"' in text
    assert 'op.drop_column("generations", "original_object_key")' in text
