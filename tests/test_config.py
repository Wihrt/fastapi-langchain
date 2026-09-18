"""Tests de chargement de la configuration."""

import pytest
from pydantic import ValidationError

from app.config import Settings


def test_lit_les_variables_denvironnement_openai(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("OPENAI_MODEL", "gemma4")
    monkeypatch.setenv("OPENAI_BASE_URL", "http://model:12434/engines/v1")

    settings = Settings()

    assert settings.api_key.get_secret_value() == "sk-test"
    assert settings.model == "gemma4"
    assert settings.base_url == "http://model:12434/engines/v1"


def test_modele_par_defaut_quand_la_variable_est_absente(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.delenv("OPENAI_MODEL", raising=False)

    assert Settings().model == "gpt-4o-mini"


def test_refuse_de_demarrer_sans_cle_api(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    with pytest.raises(ValidationError):
        Settings()


def test_la_cle_napparait_pas_dans_la_representation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-tres-secret")

    assert "sk-tres-secret" not in repr(Settings())
