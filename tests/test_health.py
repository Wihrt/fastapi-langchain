"""Test de la sonde de santé."""

from httpx import AsyncClient


async def test_healthz_repond_ok(client: AsyncClient) -> None:
    response = await client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_healthz_nest_pas_versionne(client: AsyncClient) -> None:
    assert (await client.get("/v1/healthz")).status_code == 404
