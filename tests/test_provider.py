"""Tests du provider LangChain, sans appel réseau.

Le modèle de chat est remplacé par le modèle factice de langchain-core : on
vérifie la traduction LangChain → domaine, pas le comportement d'OpenAI.
"""

from collections.abc import Sequence

from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models import BaseChatModel
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatResult as LangChainChatResult

from app.domain import ChatRequest, Message
from app.providers.langchain import LangChainChatProvider

USAGE = {"input_tokens": 3, "output_tokens": 5, "total_tokens": 8}


def build_provider(
    chat_model: BaseChatModel, models: Sequence[str] = ("modele-de-test",)
) -> LangChainChatProvider:
    return LangChainChatProvider(factory=lambda _name: chat_model, models=models)


DEFAULT_MESSAGES = (Message(role="user", content="Bonjour"),)


def build_request(
    messages: Sequence[Message] = DEFAULT_MESSAGES,
    model: str = "modele-de-test",
) -> ChatRequest:
    return ChatRequest(model=model, messages=messages)


async def test_complete_renvoie_le_contenu_du_modele() -> None:
    reply = AIMessage(content="Bonjour !", usage_metadata=USAGE)
    provider = build_provider(GenericFakeChatModel(messages=iter([reply])))

    result = await provider.complete(build_request())

    assert result.content == "Bonjour !"
    assert result.model == "modele-de-test"
    assert result.finish_reason == "stop"


async def test_complete_remonte_le_decompte_de_jetons() -> None:
    reply = AIMessage(content="Bonjour !", usage_metadata=USAGE)
    provider = build_provider(GenericFakeChatModel(messages=iter([reply])))

    usage = (await provider.complete(build_request())).usage

    assert (usage.prompt_tokens, usage.completion_tokens, usage.total_tokens) == (
        3,
        5,
        8,
    )


async def test_complete_sans_decompte_renvoie_un_usage_a_zero() -> None:
    provider = build_provider(
        GenericFakeChatModel(messages=iter([AIMessage(content="Bonjour !")]))
    )

    usage = (await provider.complete(build_request())).usage

    assert (usage.prompt_tokens, usage.completion_tokens, usage.total_tokens) == (
        0,
        0,
        0,
    )


async def test_stream_reconstitue_la_reponse_puis_signale_la_fin() -> None:
    reply = AIMessage(content="Bonjour !", usage_metadata=USAGE)
    provider = build_provider(GenericFakeChatModel(messages=iter([reply])))

    chunks = [chunk async for chunk in provider.stream(build_request())]

    assert "".join(chunk.content for chunk in chunks) == "Bonjour !"
    assert chunks[-1].finish_reason == "stop"
    assert all(chunk.finish_reason is None for chunk in chunks[:-1])


async def test_list_models_expose_les_modeles_configures() -> None:
    provider = build_provider(
        GenericFakeChatModel(messages=iter([AIMessage(content="x")])),
        models=("modele-de-test", "autre-modele"),
    )

    identifiers = [model.id for model in await provider.list_models()]

    assert identifiers == ["modele-de-test", "autre-modele"]


async def test_les_messages_du_domaine_sont_transmis_au_modele() -> None:
    captured: list[list[BaseMessage]] = []

    class RecordingChatModel(GenericFakeChatModel):
        """Modèle factice qui mémorise les messages qu'on lui passe."""

        def _generate(
            self,
            messages: list[BaseMessage],
            stop: list[str] | None = None,
            run_manager: CallbackManagerForLLMRun | None = None,
            **kwargs: object,
        ) -> LangChainChatResult:
            captured.append(list(messages))
            return super()._generate(messages, stop, run_manager, **kwargs)

    provider = build_provider(
        RecordingChatModel(messages=iter([AIMessage(content="ok")]))
    )
    request = build_request(
        messages=(
            Message(role="system", content="Tu es concis."),
            Message(role="user", content="Bonjour"),
        )
    )

    await provider.complete(request)

    roles = [message.type for message in captured[0]]
    assert roles == ["system", "human"]
