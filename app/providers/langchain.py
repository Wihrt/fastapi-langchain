"""Provider adossé à LangChain.

Traduit les types de `app.domain` en messages LangChain et inversement. Aucune
notion de HTTP ici : c'est ce qui rend les deux versions d'API interchangeables
au-dessus du même moteur.
"""

from collections.abc import AsyncIterator, Callable, Sequence

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
)
from langchain_core.runnables import Runnable

from app.domain import ChatChunk, ChatRequest, ChatResult, Message, ModelInfo, Usage

ChatModelFactory = Callable[[str], BaseChatModel]

_ROLE_TO_MESSAGE: dict[str, type[BaseMessage]] = {
    "system": SystemMessage,
    "user": HumanMessage,
    "assistant": AIMessage,
}


class LangChainChatProvider:
    """Moteur de conversation basé sur un modèle de chat LangChain."""

    name = "langchain-openai"

    def __init__(self, factory: ChatModelFactory, models: Sequence[str]) -> None:
        """Construit le provider.

        Args:
            factory: Fabrique un modèle de chat pour un identifiant donné.
            models: Modèles annoncés par `list_models`.
        """
        self._factory = factory
        self._models = tuple(models)

    async def complete(self, request: ChatRequest) -> ChatResult:
        """Interroge le modèle et renvoie la réponse complète.

        Args:
            request: Demande de complétion.

        Returns:
            La réponse du modèle, décompte de jetons inclus.
        """
        message = await self._runnable(request).ainvoke(_to_langchain(request.messages))
        return ChatResult(
            content=_text_of(message),
            model=request.model,
            finish_reason=_finish_reason_of(message) or "stop",
            usage=_usage_of(message),
        )

    async def stream(self, request: ChatRequest) -> AsyncIterator[ChatChunk]:
        """Interroge le modèle et renvoie la réponse par fragments.

        Args:
            request: Demande de complétion.

        Yields:
            Les fragments successifs ; le dernier porte `finish_reason`.
        """
        finish_reason: str | None = None
        usage: Usage | None = None
        async for chunk in self._runnable(request).astream(
            _to_langchain(request.messages)
        ):
            finish_reason = _finish_reason_of(chunk) or finish_reason
            chunk_usage = _usage_of(chunk)
            if chunk_usage != Usage():
                usage = chunk_usage
            text = _text_of(chunk)
            if text:
                yield ChatChunk(content=text)
        yield ChatChunk(content="", finish_reason=finish_reason or "stop", usage=usage)

    async def list_models(self) -> Sequence[ModelInfo]:
        """Énumère les modèles configurés.

        Returns:
            Un `ModelInfo` par modèle déclaré à la construction.
        """
        return [ModelInfo(id=identifier) for identifier in self._models]

    def _runnable(
        self, request: ChatRequest
    ) -> Runnable[list[BaseMessage], BaseMessage]:
        """Applique les paramètres d'échantillonnage de la requête au modèle."""
        model = self._factory(request.model)
        options = {
            "temperature": request.temperature,
            "top_p": request.top_p,
            "max_tokens": request.max_tokens,
            "stop": list(request.stop) if request.stop else None,
        }
        retained = {key: value for key, value in options.items() if value is not None}
        return model.bind(**retained) if retained else model


def _to_langchain(messages: Sequence[Message]) -> list[BaseMessage]:
    """Convertit les messages du domaine en messages LangChain."""
    return [
        _ROLE_TO_MESSAGE.get(message.role, HumanMessage)(content=message.content)
        for message in messages
    ]


def _text_of(message: BaseMessage) -> str:
    """Extrait le texte d'un message LangChain, quel que soit son format."""
    content = message.content
    if isinstance(content, str):
        return content
    parts = [
        block.get("text", "")
        for block in content
        if isinstance(block, dict) and block.get("type") == "text"
    ]
    return "".join(parts)


def _finish_reason_of(message: BaseMessage) -> str | None:
    """Lit la raison d'arrêt renvoyée par l'upstream, si elle est présente."""
    metadata = getattr(message, "response_metadata", None) or {}
    reason = metadata.get("finish_reason")
    return reason if isinstance(reason, str) else None


def _usage_of(message: BaseMessage) -> Usage:
    """Traduit le décompte de jetons LangChain ; zéro si l'upstream se tait."""
    metadata = getattr(message, "usage_metadata", None) or {}
    return Usage(
        prompt_tokens=int(metadata.get("input_tokens", 0)),
        completion_tokens=int(metadata.get("output_tokens", 0)),
        total_tokens=int(metadata.get("total_tokens", 0)),
    )
