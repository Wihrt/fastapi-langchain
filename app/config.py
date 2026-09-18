"""Configuration d'exécution, lue depuis l'environnement.

Les noms de variables suivent la convention OpenAI (`OPENAI_API_KEY`,
`OPENAI_MODEL`, `OPENAI_BASE_URL`) pour qu'un déploiement existant destiné à
OpenAI fonctionne sans renommage.
"""

from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Paramètres de la passerelle.

    Attributes:
        api_key: Clé transmise à l'upstream. Obligatoire : sans elle
            l'application refuse de démarrer.
        model: Modèle utilisé quand la requête n'en impose pas.
        base_url: Upstream alternatif compatible OpenAI (Docker Model Runner,
            Ollama, vLLM). Vide, l'API publique d'OpenAI est utilisée.
        log_level: Verbosité des journaux.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        protected_namespaces=(),
    )

    api_key: SecretStr = Field(validation_alias="OPENAI_API_KEY")
    model: str = Field(default="gpt-4o-mini", validation_alias="OPENAI_MODEL")
    base_url: str | None = Field(default=None, validation_alias="OPENAI_BASE_URL")
    log_level: str = Field(default="INFO", validation_alias="LOG_LEVEL")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Renvoie les paramètres, chargés une seule fois par processus.

    Returns:
        L'instance partagée de `Settings`.
    """
    return Settings()
