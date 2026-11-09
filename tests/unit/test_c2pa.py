"""C2PA: fail-closed quando required e ausencia de certificado/biblioteca."""

from __future__ import annotations

import pytest

from modules.image_generation.adapters.image_processing import C2PASigner
from shared_kernel.security_errors import C2PARequiredError


@pytest.mark.unit
def test_c2pa_required_sem_certificado_falha() -> None:
    signer = C2PASigner(enabled=True, required=True)
    with pytest.raises(C2PARequiredError):
        signer.sign(b"png")


@pytest.mark.unit
def test_c2pa_opcional_sem_certificado_publica_sem_assinatura() -> None:
    signer = C2PASigner(enabled=True, required=False)
    assert signer.sign(b"png") == b"png"


@pytest.mark.unit
def test_c2pa_desligado_nao_faz_nada() -> None:
    signer = C2PASigner(enabled=False, required=True)
    assert signer.sign(b"png") == b"png"
