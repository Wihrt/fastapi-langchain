"""Point d'entrée ASGI de la passerelle.

L'application n'est pas instanciée au chargement du module : elle est
construite par `create_app`, servie via `uvicorn app.main:create_app --factory`.
Importer le module reste ainsi sans effet de bord, y compris sans configuration.
"""

import logging

from fastapi import FastAPI

from app.api.v1.router import router as v1_router
from app.api.v2.router import router as v2_router
from app.config import get_settings
from app.errors import install_error_handlers


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

    install_error_handlers(application)
    application.include_router(v1_router)
    application.include_router(v2_router)

    @application.get("/healthz", tags=["service"])
    async def healthz() -> dict[str, str]:
        """Indique que le service est en vie."""
        return {"status": "ok"}

    return application
