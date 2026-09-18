"""Schémas HTTP de la version 2.

La version 2 reste lisible par un client OpenAI — mêmes champs, mêmes noms —
mais ajoute ce qui manque en exploitation : corrélation de requête, provider
ayant répondu, latence mesurée, et un `usage` toujours présent.

Aucun de ces modèles n'est importé depuis `app.api.v1` : les deux versions
évoluent séparément, au prix assumé d'une duplication.
"""

import json
import time
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from app.domain import ChatRequest, ChatResult, Message, ModelInfo, Usage


def new_completion_id() -> str:
    """Construit un identifiant de complétion au format OpenAI.

    Returns:
        Un identifiant préfixé par `chatcmpl-`.
    """
    return f"chatcmpl-{uuid4().hex}"


def new_request_id() -> str:
    """Construit un identifiant de corrélation.

    Returns:
        Un identifiant préfixé par `req-`.
    """
    return f"req-{uuid4().hex}"


class ChatMessage(BaseModel):
    """Un message de la conversation."""

    role: Literal["system", "user", "assistant"]
    content: str


class ChatCompletionRequest(BaseModel):
    """Corps accepté par `POST /v2/chat/completions`."""

    model_config = ConfigDict(protected_namespaces=())

    model: str | None = None
    messages: list[ChatMessage] = Field(min_length=1)
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    top_p: float | None = Field(default=None, ge=0.0, le=1.0)
    max_tokens: int | None = Field(default=None, gt=0)
    stop: str | list[str] | None = None
    stream: bool = False
    n: int = Field(default=1, ge=1, le=1)

    def to_domain(self, default_model: str) -> ChatRequest:
        """Traduit la requête HTTP en requête de domaine.

        Args:
            default_model: Modèle retenu quand le client n'en impose pas.

        Returns:
            La requête neutre passée au provider.
        """
        stop = [self.stop] if isinstance(self.stop, str) else self.stop
        return ChatRequest(
            model=self.model or default_model,
            messages=tuple(
                Message(role=message.role, content=message.content)
                for message in self.messages
            ),
            temperature=self.temperature,
            top_p=self.top_p,
            max_tokens=self.max_tokens,
            stop=tuple(stop) if stop else None,
        )


class AssistantMessage(BaseModel):
    """Message produit par le modèle."""

    role: Literal["assistant"] = "assistant"
    content: str


class Choice(BaseModel):
    """Une complétion parmi celles demandées."""

    index: int = 0
    message: AssistantMessage
    finish_reason: str


class UsageSchema(BaseModel):
    """Décompte de jetons. Toujours renseigné, quitte à valoir zéro."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0

    @classmethod
    def from_domain(cls, usage: Usage | None) -> "UsageSchema":
        """Construit le schéma depuis le décompte de domaine.

        Args:
            usage: Décompte renvoyé par le provider, éventuellement absent.

        Returns:
            Le schéma correspondant, à zéro si l'upstream s'est tu.
        """
        usage = usage or Usage()
        return cls(
            prompt_tokens=usage.prompt_tokens,
            completion_tokens=usage.completion_tokens,
            total_tokens=usage.total_tokens,
        )


class ProviderInfo(BaseModel):
    """Moteur ayant produit la réponse."""

    model_config = ConfigDict(protected_namespaces=())

    name: str
    model: str


class ChatCompletionResponse(BaseModel):
    """Réponse de `POST /v2/chat/completions`."""

    model_config = ConfigDict(protected_namespaces=())

    id: str
    object: Literal["chat.completion"] = "chat.completion"
    created: int
    model: str
    choices: list[Choice]
    usage: UsageSchema
    request_id: str
    provider: ProviderInfo
    latency_ms: int

    @classmethod
    def from_domain(
        cls,
        result: ChatResult,
        completion_id: str,
        request_id: str,
        provider_name: str,
        latency_ms: int,
    ) -> "ChatCompletionResponse":
        """Construit la réponse depuis le résultat du provider.

        Args:
            result: Résultat renvoyé par le provider.
            completion_id: Identifiant de la complétion.
            request_id: Identifiant de corrélation de la requête.
            provider_name: Nom du moteur ayant répondu.
            latency_ms: Durée mesurée côté passerelle, en millisecondes.

        Returns:
            La réponse sérialisable.
        """
        return cls(
            id=completion_id,
            created=int(time.time()),
            model=result.model,
            choices=[
                Choice(
                    message=AssistantMessage(content=result.content),
                    finish_reason=result.finish_reason,
                )
            ],
            usage=UsageSchema.from_domain(result.usage),
            request_id=request_id,
            provider=ProviderInfo(name=provider_name, model=result.model),
            latency_ms=latency_ms,
        )


class Delta(BaseModel):
    """Incrément d'un fragment de streaming."""

    model_config = ConfigDict(extra="forbid")

    role: Literal["assistant"] | None = None
    content: str | None = None


class ChunkChoice(BaseModel):
    """Complétion partielle d'un fragment de streaming."""

    index: int = 0
    delta: Delta
    finish_reason: str | None = None


class ChatCompletionChunk(BaseModel):
    """Fragment émis sur le flux SSE.

    Le fragment porte `request_id`, ce qui permet de rattacher un flux à sa
    requête dans les journaux sans attendre sa fin.
    """

    model_config = ConfigDict(protected_namespaces=())

    id: str
    object: Literal["chat.completion.chunk"] = "chat.completion.chunk"
    created: int
    model: str
    choices: list[ChunkChoice]
    request_id: str

    def to_sse(self) -> str:
        """Sérialise le fragment en événement `text/event-stream`.

        Returns:
            La ligne `data: …` terminée par une ligne vide.
        """
        payload = self.model_dump(mode="json")
        for choice in payload["choices"]:
            choice["delta"] = {
                key: value
                for key, value in choice["delta"].items()
                if value is not None
            }
        return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


class ModelSchema(BaseModel):
    """Un modèle exposé par la passerelle."""

    id: str
    object: Literal["model"] = "model"
    created: int
    owned_by: str


class ModelListResponse(BaseModel):
    """Réponse de `GET /v2/models`."""

    object: Literal["list"] = "list"
    data: list[ModelSchema]
    provider: str

    @classmethod
    def from_domain(
        cls, models: list[ModelInfo], provider_name: str
    ) -> "ModelListResponse":
        """Construit la liste depuis les modèles du domaine.

        Args:
            models: Modèles renvoyés par le provider.
            provider_name: Nom du moteur interrogé.

        Returns:
            La réponse sérialisable.
        """
        created = int(time.time())
        return cls(
            data=[
                ModelSchema(id=model.id, created=created, owned_by=model.owned_by)
                for model in models
            ],
            provider=provider_name,
        )
