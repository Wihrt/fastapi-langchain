"""Routes de la version 1 de l'API."""

import time
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.api.v1.schemas import (
    ChatCompletionChunk,
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChunkChoice,
    Delta,
    ModelListResponse,
    new_completion_id,
)
from app.config import Settings, get_settings
from app.dependencies import get_provider
from app.domain import ChatRequest
from app.errors import translate
from app.providers.base import ChatProvider

router = APIRouter(prefix="/v1", tags=["v1"])

ProviderDep = Annotated[ChatProvider, Depends(get_provider)]
SettingsDep = Annotated[Settings, Depends(get_settings)]

SSE_MEDIA_TYPE = "text/event-stream"
DONE_EVENT = "data: [DONE]\n\n"


@router.post("/chat/completions", response_model=None)
async def create_chat_completion(
    payload: ChatCompletionRequest,
    provider: ProviderDep,
    settings: SettingsDep,
) -> ChatCompletionResponse | StreamingResponse:
    """Produit une complétion de conversation.

    Args:
        payload: Requête au format OpenAI.
        provider: Moteur de conversation.
        settings: Configuration, pour le modèle par défaut.

    Returns:
        La complétion, ou un flux SSE si `stream` vaut vrai.

    Raises:
        ApiError: Si le provider échoue.
    """
    request = payload.to_domain(settings.model)
    completion_id = new_completion_id()

    if payload.stream:
        return StreamingResponse(
            await _sse_stream(provider, request, completion_id),
            media_type=SSE_MEDIA_TYPE,
        )

    try:
        result = await provider.complete(request)
    except Exception as exception:
        raise translate(exception) from exception
    return ChatCompletionResponse.from_domain(result, completion_id)


@router.get("/models", response_model=ModelListResponse)
async def list_models(provider: ProviderDep) -> ModelListResponse:
    """Énumère les modèles servis par la passerelle.

    Args:
        provider: Moteur de conversation.

    Returns:
        La liste au format OpenAI.

    Raises:
        ApiError: Si le provider échoue.
    """
    try:
        models = list(await provider.list_models())
    except Exception as exception:
        raise translate(exception) from exception
    return ModelListResponse.from_domain(models)


async def _sse_stream(
    provider: ChatProvider, request: ChatRequest, completion_id: str
) -> AsyncIterator[str]:
    """Construit le flux SSE d'une complétion.

    Le premier fragment du provider est tiré avant que la réponse ne parte :
    une panne immédiate se traduit alors en erreur HTTP propre plutôt qu'en
    flux tronqué.

    Args:
        provider: Moteur de conversation.
        request: Requête de domaine.
        completion_id: Identifiant commun à tous les fragments.

    Returns:
        Le générateur d'événements SSE.

    Raises:
        ApiError: Si le provider échoue avant le premier fragment.
    """
    chunks = provider.stream(request)
    try:
        first = await anext(chunks, None)
    except Exception as exception:
        raise translate(exception) from exception

    def envelope(choice: ChunkChoice) -> str:
        return ChatCompletionChunk(
            id=completion_id,
            created=int(time.time()),
            model=request.model,
            choices=[choice],
        ).to_sse()

    async def generate() -> AsyncIterator[str]:
        yield envelope(ChunkChoice(delta=Delta(role="assistant")))
        chunk = first
        finish_reason = "stop"
        while chunk is not None:
            if chunk.finish_reason is not None:
                finish_reason = chunk.finish_reason
            if chunk.content:
                yield envelope(ChunkChoice(delta=Delta(content=chunk.content)))
            chunk = await anext(chunks, None)
        yield envelope(ChunkChoice(delta=Delta(), finish_reason=finish_reason))
        yield DONE_EVENT

    return generate()
