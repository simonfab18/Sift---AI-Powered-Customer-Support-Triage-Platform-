from contextlib import asynccontextmanager
import logging
from time import perf_counter

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.router import api_router
from app.core.config import settings
from app.core.error_tracking import capture_exception, configure_error_tracking
from app.core.logging import configure_logging, new_request_id, reset_request_context, set_request_context
from app.db.session import init_db

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings.validate_runtime_settings()
    configure_logging()
    configure_error_tracking()
    init_db()
    yield


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    capture_exception(
        exc,
        event_name="api.unhandled_exception",
        request_id=getattr(request.state, "request_id", None),
    )
    logger.exception(
        "Unhandled API exception",
        extra={
            "event_name": "api.unhandled_exception",
            "sanitized_error": exc,
            "request_id": getattr(request.state, "request_id", None),
        },
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        debug=settings.debug,
        version=settings.release_version,
        lifespan=lifespan,
    )

    staging_origin_regex = (
        r"https://.*\.vercel\.app|http://localhost:\d+|http://127\.0\.0\.1:\d+"
        if settings.normalized_app_env == "staging"
        else None
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_origin_regex=staging_origin_regex,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def request_logging_middleware(request: Request, call_next):
        request_id = request.headers.get("x-request-id") or new_request_id()
        request.state.request_id = request_id
        content_length = request.headers.get("content-length")
        try:
            request_size = int(content_length) if content_length else 0
        except ValueError:
            request_size = 0
        if request_size > settings.max_request_body_bytes:
            return JSONResponse(
                status_code=413,
                content={"detail": "Request body too large"},
                headers={"x-request-id": request_id},
            )

        token = set_request_context(request_id)
        started = perf_counter()
        try:
            response = await call_next(request)
        finally:
            duration_ms = int((perf_counter() - started) * 1000)
            reset_request_context(token)
        response.headers["x-request-id"] = request_id
        response.headers["x-content-type-options"] = "nosniff"
        response.headers["x-frame-options"] = "DENY"
        response.headers["referrer-policy"] = "no-referrer"
        response.headers["permissions-policy"] = "geolocation=(), microphone=(), camera=()"
        if settings.is_production_like:
            response.headers["strict-transport-security"] = "max-age=31536000; includeSubDomains"
        logger.info(
            "API request completed",
            extra={
                "event_name": "api.request_completed",
                "request_id": request_id,
                "duration_ms": duration_ms,
            },
        )
        return response

    app.add_exception_handler(Exception, unhandled_exception_handler)
    app.include_router(api_router)

    return app


app = create_app()
