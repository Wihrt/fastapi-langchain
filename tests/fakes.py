"""Provider factice, substitué au provider réel dans les tests."""

from collections.abc import AsyncIterator, Sequence

from app.domain import ChatChunk, ChatRequest, ChatResult, ModelInfo, Usage


class FakeChatProvider:
    """Provider déterministe qui enregistre les requêtes reçues.

    Attributes:
        received: Requêtes passées au provider, dans l'ordre.
    """

    name = "fake"

    def __init__(
        self,
        reply: str = "Bonjour !",
        deltas: Sequence[str] = ("Bon", "jour", " !"),
        usage: Usage | None = None,
        models: Sequence[str] = ("modele-de-test", "autre-modele"),
        error: Exception | None = None,
    ) -> None:
        """Construit le provider factice.

        Args:
            reply: Contenu renvoyé par `complete`.
            deltas: Fragments successifs renvoyés par `stream`.
            usage: Décompte de jetons renvoyé ; 3/5/8 par défaut.
            models: Identifiants renvoyés par `list_models`.
            error: Exception levée par `complete` et `stream`, le cas échéant.
        """
        self.reply = reply
        self.deltas = tuple(deltas)
        self.usage = usage or Usage(
            prompt_tokens=3, completion_tokens=5, total_tokens=8
        )
        self.models = tuple(models)
        self.error = error
        self.received: list[ChatRequest] = []

    async def complete(self, request: ChatRequest) -> ChatResult:
        """Renvoie une réponse fixe et mémorise la requête."""
        self.received.append(request)
        if self.error is not None:
            raise self.error
        return ChatResult(
            content=self.reply,
            model=request.model,
            finish_reason="stop",
            usage=self.usage,
        )

    async def stream(self, request: ChatRequest) -> AsyncIterator[ChatChunk]:
        """Émet les fragments configurés puis un chunk de fin."""
        self.received.append(request)
        if self.error is not None:
            raise self.error
        for delta in self.deltas:
            yield ChatChunk(content=delta)
        yield ChatChunk(content="", finish_reason="stop", usage=self.usage)

    async def list_models(self) -> Sequence[ModelInfo]:
        """Renvoie la liste de modèles configurée."""
        return [ModelInfo(id=identifier) for identifier in self.models]
