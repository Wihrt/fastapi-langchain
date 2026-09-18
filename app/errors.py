"""Erreurs au format OpenAI.

Toute sortie en erreur de la passerelle, quelle que soit la version d'API,
porte l'enveloppe `{"error": {"message", "type", "param", "code"}}` : c'est ce
qu'attendent les clients OpenAI, y compris pour les erreurs de validation.
"""

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

UPSTREAM_FAILURE_MESSAGE = "Le service amont n'a pas pu traiter la requête."
SERVER_ERROR_THRESHOLD = 500

_STATUS_TO_TYPE = {
    400: "invalid_request_error",
    401: "authentication_error",
    403: "permission_error",
    404: "invalid_request_error",
    409: "invalid_request_error",
    422: "invalid_request_error",
    429: "rate_limit_error",
}


class UpstreamError(Exception):
    """Panne signalée par le service amont.

    Attributes:
        status_code: Statut renvoyé par l'upstream.
    """

    def __init__(self, message: str, status_code: int = 502) -> None:
        """Construit l'erreur.

        Args:
            message: Description destinée au client.
            status_code: Statut HTTP renvoyé par l'upstream.
        """
        super().__init__(message)
        self.status_code = status_code


class ApiError(Exception):
    """Erreur déjà traduite, prête à être sérialisée.

    Attributes:
        status_code: Statut HTTP à renvoyer.
        message: Message destiné au client.
        error_type: Valeur du champ `type` de l'enveloppe.
        param: Champ de la requête en cause, le cas échéant.
        code: Code d'erreur applicatif, le cas échéant.
    """

    def __init__(
        self,
        status_code: int,
        message: str,
        error_type: str | None = None,
        param: str | None = None,
        code: str | None = None,
    ) -> None:
        """Construit l'erreur.

        Args:
            status_code: Statut HTTP à renvoyer.
            message: Message destiné au client.
            error_type: Type OpenAI ; déduit du statut s'il est omis.
            param: Champ de la requête en cause.
            code: Code d'erreur applicatif.
        """
        super().__init__(message)
        self.status_code = status_code
        self.message = message
        self.error_type = error_type or _STATUS_TO_TYPE.get(status_code, "api_error")
        self.param = param
        self.code = code


def translate(exception: Exception) -> ApiError:
    """Traduit une panne de provider en erreur exposable.

    Le message d'une exception inattendue n'est jamais repris : il peut porter
    une URL d'upstream, un en-tête d'authentification ou une clé.

    Args:
        exception: Exception levée par le provider.

    Returns:
        L'erreur à renvoyer au client.
    """
    if isinstance(exception, ApiError):
        return exception
    if isinstance(exception, UpstreamError):
        status = (
            exception.status_code
            if exception.status_code < SERVER_ERROR_THRESHOLD
            else 502
        )
        return ApiError(status_code=status, message=str(exception))
    return ApiError(status_code=502, message=UPSTREAM_FAILURE_MESSAGE)


def error_payload(
    message: str,
    error_type: str,
    param: str | None = None,
    code: str | None = None,
) -> dict[str, dict[str, str | None]]:
    """Construit le corps d'une réponse en erreur.

    Args:
        message: Message destiné au client.
        error_type: Type OpenAI de l'erreur.
        param: Champ de la requête en cause.
        code: Code d'erreur applicatif.

    Returns:
        L'enveloppe `{"error": {...}}`.
    """
    return {
        "error": {
            "message": message,
            "type": error_type,
            "param": param,
            "code": code,
        }
    }


def install_error_handlers(application: FastAPI) -> None:
    """Branche les gestionnaires d'erreurs sur l'application.

    Args:
        application: Application à équiper.
    """

    @application.exception_handler(ApiError)
    async def _api_error(_: Request, exception: ApiError) -> JSONResponse:
        return JSONResponse(
            status_code=exception.status_code,
            content=error_payload(
                exception.message,
                exception.error_type,
                exception.param,
                exception.code,
            ),
        )

    @application.exception_handler(RequestValidationError)
    async def _validation_error(
        _: Request, exception: RequestValidationError
    ) -> JSONResponse:
        # OpenAI répond 400 là où FastAPI répondrait 422.
        first = exception.errors()[0]
        return JSONResponse(
            status_code=400,
            content=error_payload(
                first.get("msg", "Requête invalide."),
                "invalid_request_error",
                param=_param_of(first.get("loc", ())),
            ),
        )

    @application.exception_handler(StarletteHTTPException)
    async def _http_error(
        _: Request, exception: StarletteHTTPException
    ) -> JSONResponse:
        return JSONResponse(
            status_code=exception.status_code,
            content=error_payload(
                str(exception.detail),
                _STATUS_TO_TYPE.get(exception.status_code, "api_error"),
            ),
        )


def _param_of(location: object) -> str | None:
    """Extrait le nom du champ fautif d'une position d'erreur pydantic."""
    if not isinstance(location, tuple | list):
        return None
    parts = [part for part in location if isinstance(part, str) and part != "body"]
    return parts[0] if parts else None
