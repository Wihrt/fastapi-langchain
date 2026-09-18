"""Conformité de `/v1` au contrat OpenAI."""

from httpx import AsyncClient

from tests.fakes import FakeChatProvider

PROMPT = {"role": "user", "content": "Bonjour"}


async def test_reponse_conforme_au_schema_openai(client: AsyncClient) -> None:
    response = await client.post(
        "/v1/chat/completions",
        json={"model": "gpt-4o-mini", "messages": [PROMPT]},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["object"] == "chat.completion"
    assert body["id"].startswith("chatcmpl-")
    assert body["model"] == "gpt-4o-mini"
    assert isinstance(body["created"], int)
    assert body["choices"] == [
        {
            "index": 0,
            "message": {"role": "assistant", "content": "Bonjour !"},
            "finish_reason": "stop",
        }
    ]
    assert body["usage"] == {
        "prompt_tokens": 3,
        "completion_tokens": 5,
        "total_tokens": 8,
    }


async def test_la_reponse_v1_ne_porte_aucune_extension(client: AsyncClient) -> None:
    body = (
        await client.post(
            "/v1/chat/completions",
            json={"model": "gpt-4o-mini", "messages": [PROMPT]},
        )
    ).json()

    assert set(body) == {"id", "object", "created", "model", "choices", "usage"}


async def test_les_messages_sont_transmis_au_provider(
    client: AsyncClient, provider: FakeChatProvider
) -> None:
    await client.post(
        "/v1/chat/completions",
        json={
            "model": "gpt-4o-mini",
            "messages": [
                {"role": "system", "content": "Tu es concis."},
                PROMPT,
            ],
            "temperature": 0.2,
            "max_tokens": 64,
        },
    )

    request = provider.received[0]
    assert [(m.role, m.content) for m in request.messages] == [
        ("system", "Tu es concis."),
        ("user", "Bonjour"),
    ]
    assert request.temperature == 0.2
    assert request.max_tokens == 64


async def test_le_modele_est_facultatif_et_vient_de_lenvironnement(
    client: AsyncClient, provider: FakeChatProvider
) -> None:
    response = await client.post("/v1/chat/completions", json={"messages": [PROMPT]})

    assert response.status_code == 200
    assert provider.received[0].model == "modele-de-test"
    assert response.json()["model"] == "modele-de-test"


async def test_liste_des_modeles(client: AsyncClient) -> None:
    response = await client.get("/v1/models")

    assert response.status_code == 200
    body = response.json()
    assert body["object"] == "list"
    assert [model["id"] for model in body["data"]] == [
        "modele-de-test",
        "autre-modele",
    ]
    assert all(model["object"] == "model" for model in body["data"])
