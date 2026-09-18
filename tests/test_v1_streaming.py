"""Conformité du streaming SSE de `/v1` au format OpenAI."""

import json

from httpx import AsyncClient

PAYLOAD = {
    "model": "gpt-4o-mini",
    "messages": [{"role": "user", "content": "Bonjour"}],
    "stream": True,
}


async def collect_events(client: AsyncClient) -> list[str]:
    """Renvoie les charges utiles `data:` d'une réponse SSE, dans l'ordre."""
    async with client.stream("POST", "/v1/chat/completions", json=PAYLOAD) as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        body = "".join([part async for part in response.aiter_text()])
    return [
        line.removeprefix("data: ")
        for line in body.splitlines()
        if line.startswith("data: ")
    ]


async def test_le_flux_se_termine_par_le_sentinelle_done(client: AsyncClient) -> None:
    events = await collect_events(client)

    assert events[-1] == "[DONE]"


async def test_les_fragments_sont_des_chunks_de_completion(
    client: AsyncClient,
) -> None:
    events = await collect_events(client)
    chunks = [json.loads(event) for event in events[:-1]]

    assert all(chunk["object"] == "chat.completion.chunk" for chunk in chunks)
    assert len({chunk["id"] for chunk in chunks}) == 1
    assert all(chunk["id"].startswith("chatcmpl-") for chunk in chunks)


async def test_le_premier_fragment_annonce_le_role(client: AsyncClient) -> None:
    first = json.loads((await collect_events(client))[0])

    assert first["choices"][0]["delta"]["role"] == "assistant"
    assert first["choices"][0]["finish_reason"] is None


async def test_le_texte_se_reconstitue_dans_lordre(client: AsyncClient) -> None:
    chunks = [json.loads(event) for event in (await collect_events(client))[:-1]]

    texte = "".join(chunk["choices"][0]["delta"].get("content", "") for chunk in chunks)
    assert texte == "Bonjour !"


async def test_le_dernier_fragment_porte_la_raison_darret(
    client: AsyncClient,
) -> None:
    chunks = [json.loads(event) for event in (await collect_events(client))[:-1]]

    assert chunks[-1]["choices"][0]["finish_reason"] == "stop"
    assert chunks[-1]["choices"][0]["delta"] == {}
    assert all(chunk["choices"][0]["finish_reason"] is None for chunk in chunks[:-1])
