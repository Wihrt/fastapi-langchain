"""Types échangés entre les routers et les providers.

Ces types sont volontairement neutres : ils ne dépendent ni de FastAPI ni de
LangChain. C'est ce qui permet à `/v1` et `/v2` d'avoir des schémas HTTP
totalement disjoints tout en partageant un seul provider.
"""

from collections.abc import Sequence
from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class Message:
    """Un tour de conversation.

    Attributes:
        role: `system`, `user` ou `assistant`.
        content: Texte du message.
    """

    role: str
    content: str


@dataclass(frozen=True, slots=True)
class Usage:
    """Décompte de jetons d'un échange.

    Attributes:
        prompt_tokens: Jetons consommés par l'invite.
        completion_tokens: Jetons produits par le modèle.
        total_tokens: Somme des deux.
    """

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


@dataclass(frozen=True, slots=True)
class ChatRequest:
    """Demande de complétion, indépendante de la version d'API.

    Attributes:
        model: Modèle demandé.
        messages: Historique fourni par le client.
        temperature: Température d'échantillonnage.
        top_p: Troncature nucleus.
        max_tokens: Plafond de jetons produits.
        stop: Séquences d'arrêt.
    """

    model: str
    messages: Sequence[Message]
    temperature: float | None = None
    top_p: float | None = None
    max_tokens: int | None = None
    stop: Sequence[str] | None = None


@dataclass(frozen=True, slots=True)
class ChatResult:
    """Réponse complète d'un modèle.

    Attributes:
        content: Texte produit.
        model: Modèle ayant répondu.
        finish_reason: Raison d'arrêt (`stop`, `length`, ...).
        usage: Décompte de jetons.
    """

    content: str
    model: str
    finish_reason: str = "stop"
    usage: Usage = field(default_factory=Usage)


@dataclass(frozen=True, slots=True)
class ChatChunk:
    """Fragment de réponse en streaming.

    Attributes:
        content: Incrément de texte, vide sur le fragment terminal.
        finish_reason: Renseigné uniquement sur le fragment terminal.
        usage: Décompte de jetons, si l'upstream le fournit.
    """

    content: str
    finish_reason: str | None = None
    usage: Usage | None = None


@dataclass(frozen=True, slots=True)
class ModelInfo:
    """Modèle exposé par la passerelle.

    Attributes:
        id: Identifiant du modèle.
        owned_by: Propriétaire déclaré.
    """

    id: str
    owned_by: str = "fastapi-langchain"
