"""Routes de la version 2 de l'API."""

import time
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Response
from fastapi.responses import StreamingResponse

from app.api.v2.schemas import (
    ChatCompletionChunk,
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChunkChoice,
    Delta,
    ModelListResponse,
    new_completion_id,
    new_request_id,
)
from app.config import Settings, get_settings
from app.dependencies import get_provider
from app.domain import ChatRequest
from app.errors import translate
from app.providers.base import ChatProvider

router = APIRouter(prefix="/v2", tags=["v2"])

ProviderDep = Annotated[ChatProvider, Depends(get_provider)]
SettingsDep = Annotated[Settings, Depends(get_settings)]
RequestIdHeader = Annotated[str | None, Header(alias="X-Request-ID")]

SSE_MEDIA_TYPE = "text/event-stream"
DONE_EVENT = "data: [DONE]\n\n"
REQUEST_ID_HEADER = "X-Request-ID"


@router.post("/chat/completions", response_model=None)
async def create_chat_completion(
    payload: ChatCompletionRequest,
    provider: ProviderDep,
    settings: SettingsDep,
    response: Response,
    x_request_id: RequestIdHeader = None,
) -> ChatCompletionResponse | StreamingResponse:
    """Produit une complétion de conversation, enrichie pour l'exploitation.

    Args:
        payload: Requête au format OpenAI.
        provider: Moteur de conversation.
        settings: Configuration, pour le modèle par défaut.
        response: Réponse, pour y poser l'en-tête de corrélation.
        x_request_id: Identifiant de corrélation fourni par le client.

    Returns:
        La complétion enrichie, ou un flux SSE si `stream` vaut vrai.

    Raises:
        ApiError: Si le provider échoue.
    """
    request = payload.to_domain(settings.model)
    completion_id = new_completion_id()
    request_id = x_request_id or new_request_id()

    if payload.stream:
        stream = await _sse_stream(provider, request, completion_id, request_id)
        return StreamingResponse(
            stream,
            media_type=SSE_MEDIA_TYPE,
            headers={REQUEST_ID_HEADER: request_id},
        )

    started = time.perf_counter()
    try:
        result = await provider.complete(request)
    except Exception as exception:
        raise translate(exception) from exception
    latency_ms = int((time.perf_counter() - started) * 1000)

    response.headers[REQUEST_ID_HEADER] = request_id
    return ChatCompletionResponse.from_domain(
        result,
        completion_id=completion_id,
        request_id=request_id,
        provider_name=provider.name,
        latency_ms=latency_ms,
    )


@router.get("/models", response_model=ModelListResponse)
async def list_models(provider: ProviderDep) -> ModelListResponse:
    """Énumère les modèles servis, en nommant le moteur interrogé.

    Args:
        provider: Moteur de conversation.

    Returns:
        La liste enrichie du nom du provider.

    Raises:
        ApiError: Si le provider échoue.
    """
    try:
        models = list(await provider.list_models())
    except Exception as exception:
        raise translate(exception) from exception
    return ModelListResponse.from_domain(models, provider.name)


async def _sse_stream(
    provider: ChatProvider,
    request: ChatRequest,
    completion_id: str,
    request_id: str,
) -> AsyncIterator[str]:
    """Construit le flux SSE d'une complétion.

    Args:
        provider: Moteur de conversation.
        request: Requête de domaine.
        completion_id: Identifiant commun à tous les fragments.
        request_id: Identifiant de corrélation porté par chaque fragment.

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
            request_id=request_id,
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
