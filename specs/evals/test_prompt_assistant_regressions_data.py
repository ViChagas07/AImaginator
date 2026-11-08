"""Dados de regressao do assistente (nao chama LLM)."""

from __future__ import annotations

from collections import Counter

from specs.evals.prompt_assistant_eval import REGRESSION_CASES


def test_regressao_cobre_11_locales_e_3_grupos() -> None:
    assert len(REGRESSION_CASES) == 33
    assert len({case["locale"] for case in REGRESSION_CASES}) == 11
    assert Counter(case["expected"] for case in REGRESSION_CASES) == {
        "nsfw": 11,
        "self_harm": 11,
        "pass": 11,
    }
    ids = {case["id"] for case in REGRESSION_CASES}
    assert len(ids) == 33
    for case in REGRESSION_CASES:
        assert case["text"].strip()
        if case["expected"] == "nsfw":
            assert case["must_not_be"] == "self_harm"
        elif case["expected"] == "self_harm":
            assert case["must_not_be"] == "nsfw"
        else:
            assert case.get("check_rewrite") is True
