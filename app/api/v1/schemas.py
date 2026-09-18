"""Schémas HTTP de la version 1 : contrat OpenAI, strictement.

Ces modèles ne sont partagés avec aucune autre version : `/v2` a les siens.
C'est ce qui permet de figer `/v1` sur le contrat d'OpenAI pendant que `/v2`
évolue.
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


class ChatMessage(BaseModel):
    """Un message de la conversation."""

    role: Literal["system", "user", "assistant"]
    content: str


class ChatCompletionRequest(BaseModel):
    """Corps accepté par `POST /v1/chat/completions`."""

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
    """Décompte de jetons de l'échange."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0

    @classmethod
    def from_domain(cls, usage: Usage) -> "UsageSchema":
        """Construit le schéma depuis le décompte de domaine.

        Args:
            usage: Décompte renvoyé par le provider.

        Returns:
            Le schéma correspondant.
        """
        return cls(
            prompt_tokens=usage.prompt_tokens,
            completion_tokens=usage.completion_tokens,
            total_tokens=usage.total_tokens,
        )


class ChatCompletionResponse(BaseModel):
    """Réponse de `POST /v1/chat/completions`."""

    model_config = ConfigDict(protected_namespaces=())

    id: str
    object: Literal["chat.completion"] = "chat.completion"
    created: int
    model: str
    choices: list[Choice]
    usage: UsageSchema

    @classmethod
    def from_domain(
        cls, result: ChatResult, completion_id: str
    ) -> "ChatCompletionResponse":
        """Construit la réponse depuis le résultat du provider.

        Args:
            result: Résultat renvoyé par le provider.
            completion_id: Identifiant de la complétion.

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
    """Fragment émis sur le flux SSE."""

    model_config = ConfigDict(protected_namespaces=())

    id: str
    object: Literal["chat.completion.chunk"] = "chat.completion.chunk"
    created: int
    model: str
    choices: list[ChunkChoice]

    def to_sse(self) -> str:
        """Sérialise le fragment en événement `text/event-stream`.

        Les clés absentes du `delta` sont retirées — OpenAI n'envoie `role` que
        sur le premier fragment — mais `finish_reason` reste présent à `null`
        tant que le flux n'est pas terminé, comme chez OpenAI.

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
    """Réponse de `GET /v1/models`."""

    object: Literal["list"] = "list"
    data: list[ModelSchema]

    @classmethod
    def from_domain(cls, models: list[ModelInfo]) -> "ModelListResponse":
        """Construit la liste depuis les modèles du domaine.

        Args:
            models: Modèles renvoyés par le provider.

        Returns:
            La réponse sérialisable.
        """
        created = int(time.time())
        return cls(
            data=[
                ModelSchema(id=model.id, created=created, owned_by=model.owned_by)
                for model in models
            ]
        )
