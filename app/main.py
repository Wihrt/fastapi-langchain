"""Point d'entrée ASGI de la passerelle.

L'application n'est pas instanciée au chargement du module : elle est
construite par `create_app`, servie via `uvicorn app.main:create_app --factory`.
Importer le module reste ainsi sans effet de bord, y compris sans configuration.
"""

import logging

from fastapi import FastAPI

from app.config import get_settings


def create_app() -> FastAPI:
    """Construit l'application FastAPI.

    Les paramètres sont lus ici : une clé d'API absente fait échouer la
    construction plutôt que la première requête.

    Returns:
        L'application prête à être servie.
    """
    settings = get_settings()
    logging.basicConfig(level=settings.log_level.upper())

    application = FastAPI(
        title="Passerelle chatbot compatible OpenAI",
        version="0.1.0",
        summary="Interface OpenAI servie par FastAPI et LangChain.",
    )

    @application.get("/healthz", tags=["service"])
    async def healthz() -> dict[str, str]:
        """Indique que le service est en vie."""
        return {"status": "ok"}

    return application
