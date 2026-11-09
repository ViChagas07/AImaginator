"""Ownership anonimo no fluxo HTTP: token do POST controla GET e cancel."""

from __future__ import annotations

import pytest

from tests.integration.test_api import api_client  # noqa: F401  (fixture compartilhada)


@pytest.mark.integration
def test_token_anonimo_do_post_controla_get_e_cancel(api_client) -> None:  # noqa: F811
    client, _ = api_client
    created = client.post(
        "/api/v1/generations",
        json={
            "prompt": "uma cabana na floresta",
            "style_preset": "none",
            "aspect_ratio": "1:1",
        },
    )
    assert created.status_code == 202, created.text
    body = created.json()
    generation_id = body["id"]
    anonymous_token = body.get("anonymous_token")
    assert isinstance(anonymous_token, str) and anonymous_token

    client.cookies.clear()
    assert client.get(f"/api/v1/generations/{generation_id}").status_code == 403
    assert (
        client.get(
            f"/api/v1/generations/{generation_id}",
            headers={"X-Anonymous-Session": "wrong-token"},
        ).status_code
        == 403
    )
    owned = client.get(
        f"/api/v1/generations/{generation_id}",
        headers={"X-Anonymous-Session": anonymous_token},
    )
    assert owned.status_code == 200

    canceled = client.post(
        f"/api/v1/generations/{generation_id}/cancel",
        headers={"X-Anonymous-Session": anonymous_token},
    )
    assert canceled.status_code == 200, canceled.text
    assert canceled.json()["status"] == "canceled"
    assert canceled.json()["canceled"] is True

    final = client.get(
        f"/api/v1/generations/{generation_id}",
        headers={"X-Anonymous-Session": anonymous_token},
    )
    assert final.status_code == 200
    assert final.json()["status"] == "canceled"
