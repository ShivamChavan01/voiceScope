from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from api.routes import router
from middleware.auth import APIKeyAuthMiddleware
from middleware.rate_limit import RateLimitMiddleware
from utils.tracing import RequestContext, set_request_context
from utils.logger import set_correlation_id
import uuid
import os


load_dotenv()

IS_PRODUCTION = os.getenv("APP_ENV") == "production"

app = FastAPI(
    title="VoiceScope",
    description="Open source observability API for voice AI agents. Multi-provider LLM support, plugin system, and comprehensive analytics.",
    version="2.3.0",
    docs_url="/docs" if not IS_PRODUCTION else None,
    redoc_url="/redoc" if not IS_PRODUCTION else None,
)

ALLOWED_ORIGINS = [
    origin.strip() for origin in os.getenv("CORS_ORIGINS", "").split(",") if origin.strip()
]

if ALLOWED_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=ALLOWED_ORIGINS,
        allow_methods=["GET", "POST"],
        allow_headers=["X-API-Key", "Content-Type", "X-Correlation-ID"],
    )

app.add_middleware(RateLimitMiddleware)
app.add_middleware(APIKeyAuthMiddleware)


@app.middleware("http")
async def request_context_middleware(request: Request, call_next):
    correlation_id = request.headers.get("X-Correlation-ID", str(uuid.uuid4()))
    set_correlation_id(correlation_id)

    ctx = RequestContext(
        run_id=str(uuid.uuid4()),
        correlation_id=correlation_id,
    )
    set_request_context(ctx)

    response = await call_next(request)
    response.headers["X-Correlation-ID"] = correlation_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    if isinstance(exc, HTTPException):
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
    from utils.logger import logger

    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


app.include_router(router, prefix="/api/v1")


@app.get("/")
async def root():
    return {
        "service": "VoiceScope",
        "version": "2.0.0",
        "docs": "/docs" if not IS_PRODUCTION else "disabled",
        "health": "/api/v1/health",
        "analyze": "POST /api/v1/analyze",
        "providers": ["openai", "anthropic", "gemini", "ollama", "mistral"],
    }
