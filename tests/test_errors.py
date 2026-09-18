"""Traduction des pannes en erreurs au format OpenAI."""

import pytest
from httpx import ASGITransport, AsyncClient

from app.config import get_settings
from app.dependencies import get_provider
from app.errors import UpstreamError
from app.main import create_app
from tests.fakes import FakeChatProvider

PROMPT = {"role": "user", "content": "Bonjour"}


async def client_with_error(
    monkeypatch: pytest.MonkeyPatch, error: Exception
) -> AsyncClient:
    """Construit un client dont le provider échoue systématiquement."""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("OPENAI_MODEL", "modele-de-test")
    get_settings.cache_clear()
    application = create_app()
    provider = FakeChatProvider(error=error)
    application.dependency_overrides[get_provider] = lambda: provider
    return AsyncClient(transport=ASGITransport(app=application), base_url="http://test")


async def test_corps_invalide_renvoie_400_au_format_openai(
    client: AsyncClient,
) -> None:
    response = await client.post("/v1/chat/completions", json={"messages": []})

    assert response.status_code == 400
    error = response.json()["error"]
    assert error["type"] == "invalid_request_error"
    assert error["param"] == "messages"
    assert isinstance(error["message"], str)


async def test_champ_de_mauvais_type_renvoie_400(client: AsyncClient) -> None:
    response = await client.post(
        "/v1/chat/completions",
        json={"messages": [PROMPT], "temperature": "chaud"},
    )

    assert response.status_code == 400
    assert response.json()["error"]["param"] == "temperature"


@pytest.mark.parametrize(
    ("status_amont", "statut_attendu", "type_attendu"),
    [
        (401, 401, "authentication_error"),
        (429, 429, "rate_limit_error"),
        (500, 502, "api_error"),
    ],
)
async def test_les_pannes_amont_sont_traduites(
    monkeypatch: pytest.MonkeyPatch,
    status_amont: int,
    statut_attendu: int,
    type_attendu: str,
) -> None:
    error = UpstreamError("l'upstream a refusé", status_code=status_amont)
    async with await client_with_error(monkeypatch, error) as client:
        response = await client.post(
            "/v1/chat/completions", json={"messages": [PROMPT]}
        )

    assert response.status_code == statut_attendu
    assert response.json()["error"]["type"] == type_attendu


async def test_une_panne_inattendue_devient_502(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async with await client_with_error(monkeypatch, RuntimeError("boum")) as client:
        response = await client.post(
            "/v1/chat/completions", json={"messages": [PROMPT]}
        )

    assert response.status_code == 502
    assert response.json()["error"]["type"] == "api_error"


async def test_le_message_dune_panne_amont_ne_fuit_pas(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fuite = "Bearer sk-tres-confidentiel"
    async with await client_with_error(monkeypatch, RuntimeError(fuite)) as client:
        response = await client.post(
            "/v1/chat/completions", json={"messages": [PROMPT]}
        )

    assert fuite not in response.text


async def test_route_inconnue_renvoie_lenveloppe_openai(client: AsyncClient) -> None:
    response = await client.get("/v1/inexistant")

    assert response.status_code == 404
    assert response.json()["error"]["type"] == "invalid_request_error"
