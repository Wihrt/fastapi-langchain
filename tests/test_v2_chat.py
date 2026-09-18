"""Extensions de la version 2, et indépendance vis-à-vis de la version 1."""

import json

from httpx import AsyncClient

from app.api.v1 import schemas as v1_schemas
from app.api.v2 import schemas as v2_schemas

PROMPT = {"role": "user", "content": "Bonjour"}
BODY = {"model": "gpt-4o-mini", "messages": [PROMPT]}


async def test_v2_reste_compatible_avec_un_client_openai(
    client: AsyncClient,
) -> None:
    body = (await client.post("/v2/chat/completions", json=BODY)).json()

    assert body["object"] == "chat.completion"
    assert body["choices"][0]["message"] == {
        "role": "assistant",
        "content": "Bonjour !",
    }
    assert body["usage"]["total_tokens"] == 8


async def test_v2_ajoute_le_provider_la_latence_et_le_request_id(
    client: AsyncClient,
) -> None:
    response = await client.post("/v2/chat/completions", json=BODY)
    body = response.json()

    assert body["provider"] == {"name": "fake", "model": "gpt-4o-mini"}
    assert isinstance(body["latency_ms"], int)
    assert body["latency_ms"] >= 0
    assert body["request_id"] == response.headers["x-request-id"]


async def test_v2_reprend_le_request_id_fourni_par_le_client(
    client: AsyncClient,
) -> None:
    response = await client.post(
        "/v2/chat/completions", json=BODY, headers={"X-Request-ID": "trace-42"}
    )

    assert response.json()["request_id"] == "trace-42"
    assert response.headers["x-request-id"] == "trace-42"


async def test_v1_nherite_daucune_extension_de_v2(client: AsyncClient) -> None:
    body = (await client.post("/v1/chat/completions", json=BODY)).json()

    assert "provider" not in body
    assert "latency_ms" not in body
    assert "request_id" not in body


async def test_v2_expose_toujours_un_usage_meme_absent_de_lamont(
    client: AsyncClient,
) -> None:
    body = (await client.post("/v2/chat/completions", json=BODY)).json()

    assert set(body["usage"]) == {
        "prompt_tokens",
        "completion_tokens",
        "total_tokens",
    }


async def test_v2_diffuse_aussi_en_sse(client: AsyncClient) -> None:
    payload = BODY | {"stream": True}
    async with client.stream("POST", "/v2/chat/completions", json=payload) as response:
        assert response.status_code == 200
        texte = "".join([part async for part in response.aiter_text()])

    events = [
        line.removeprefix("data: ")
        for line in texte.splitlines()
        if line.startswith("data: ")
    ]
    chunks = [json.loads(event) for event in events[:-1]]
    assert events[-1] == "[DONE]"
    assert all(chunk["object"] == "chat.completion.chunk" for chunk in chunks)
    assert (
        "".join(chunk["choices"][0]["delta"].get("content", "") for chunk in chunks)
        == "Bonjour !"
    )


async def test_v2_liste_les_modeles(client: AsyncClient) -> None:
    body = (await client.get("/v2/models")).json()

    assert body["object"] == "list"
    assert [model["id"] for model in body["data"]] == [
        "modele-de-test",
        "autre-modele",
    ]
    assert body["provider"] == "fake"


async def test_les_schemas_des_deux_versions_sont_disjoints() -> None:
    assert v1_schemas.ChatCompletionResponse is not v2_schemas.ChatCompletionResponse
    assert v1_schemas.ChatCompletionRequest is not v2_schemas.ChatCompletionRequest
