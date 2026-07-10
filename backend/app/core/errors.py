"""RFC7807-style error envelope: { error_code, message, field_errors } applied consistently
across the API — raised via `AppError`, and also normalizes FastAPI's built-in
`HTTPException`/`RequestValidationError` into the same shape."""

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


class AppError(Exception):
    """Raise this from route handlers/dependencies for any non-2xx response instead of an
    ad-hoc `HTTPException` body — keeps the RFC7807 envelope consistent everywhere."""

    def __init__(
        self,
        status_code: int,
        error_code: str,
        message: str,
        field_errors: dict[str, str] | None = None,
    ) -> None:
        self.status_code = status_code
        self.error_code = error_code
        self.message = message
        self.field_errors = field_errors
        super().__init__(message)


def _problem_response(status_code: int, error_code: str, message: str, field_errors=None):
    return JSONResponse(
        status_code=status_code,
        content={"error_code": error_code, "message": message, "field_errors": field_errors},
    )


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError):
        return _problem_response(exc.status_code, exc.error_code, exc.message, exc.field_errors)

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        detail = exc.detail
        if isinstance(detail, dict) and "error_code" in detail:
            return _problem_response(
                exc.status_code,
                detail["error_code"],
                detail.get("message", detail["error_code"]),
                detail.get("field_errors"),
            )
        return _problem_response(exc.status_code, "HTTP_ERROR", str(detail))

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        field_errors: dict[str, str] = {}
        for err in exc.errors():
            loc = ".".join(str(p) for p in err["loc"] if p != "body")
            field_errors[loc or "__root__"] = err["msg"]
        return _problem_response(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "VALIDATION_ERROR",
            "Request validation failed.",
            field_errors,
        )
