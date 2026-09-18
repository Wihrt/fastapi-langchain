"""Fixtures communes aux tests d'API."""

from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient

from app.config import get_settings
from app.dependencies import get_provider
from app.main import create_app
from tests.fakes import FakeChatProvider

DEFAULT_MODEL = "modele-de-test"


@pytest.fixture
def provider() -> FakeChatProvider:
    """Provider factice injecté à la place du provider réel."""
    return FakeChatProvider()


@pytest.fixture
async def client(
    monkeypatch: pytest.MonkeyPatch, provider: FakeChatProvider
) -> AsyncIterator[AsyncClient]:
    """Client HTTP branché sur l'application, provider factice injecté."""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("OPENAI_MODEL", DEFAULT_MODEL)
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    get_settings.cache_clear()

    application = create_app()
    application.dependency_overrides[get_provider] = lambda: provider

    transport = ASGITransport(app=application)
    async with AsyncClient(transport=transport, base_url="http://test") as http_client:
        yield http_client

    get_settings.cache_clear()
