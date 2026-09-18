"""Contrat que doit remplir un moteur de conversation."""

from collections.abc import AsyncIterator, Sequence
from typing import Protocol, runtime_checkable

from app.domain import ChatChunk, ChatRequest, ChatResult, ModelInfo


@runtime_checkable
class ChatProvider(Protocol):
    """Moteur de conversation vu par les routers.

    Un provider ne connaît aucun schéma HTTP : il reçoit et renvoie
    exclusivement les types de `app.domain`.
    """

    name: str

    async def complete(self, request: ChatRequest) -> ChatResult:
        """Produit une réponse complète.

        Args:
            request: Demande de complétion.

        Returns:
            La réponse du modèle.
        """
        ...

    def stream(self, request: ChatRequest) -> AsyncIterator[ChatChunk]:
        """Produit la réponse par fragments.

        Args:
            request: Demande de complétion.

        Returns:
            Les fragments successifs ; le dernier porte `finish_reason`.
        """
        ...

    async def list_models(self) -> Sequence[ModelInfo]:
        """Énumère les modèles exposés par la passerelle.

        Returns:
            Les modèles disponibles.
        """
        ...
