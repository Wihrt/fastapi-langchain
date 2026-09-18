"""Fourniture des dépendances aux routers.

`get_provider` est le point d'injection : les tests le remplacent par un
provider factice via `app.dependency_overrides`.
"""

from functools import lru_cache

from langchain_core.language_models import BaseChatModel
from langchain_openai import ChatOpenAI

from app.config import Settings, get_settings
from app.providers.base import ChatProvider
from app.providers.langchain import LangChainChatProvider


@lru_cache(maxsize=1)
def get_provider() -> ChatProvider:
    """Renvoie le provider de l'application.

    Returns:
        Le provider LangChain configuré depuis l'environnement.
    """
    return build_provider(get_settings())


def build_provider(settings: Settings) -> ChatProvider:
    """Construit un provider LangChain à partir des paramètres.

    Args:
        settings: Configuration de la passerelle.

    Returns:
        Un provider prêt à l'emploi.
    """

    @lru_cache(maxsize=8)
    def factory(model: str) -> BaseChatModel:
        return ChatOpenAI(
            model=model,
            api_key=settings.api_key,
            base_url=settings.base_url,
            stream_usage=True,
        )

    return LangChainChatProvider(factory=factory, models=(settings.model,))
