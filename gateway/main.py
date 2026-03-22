"""
AI Inference Gateway — Main Application

Sits in front of AIClient-2-API to provide:
  - User management and API key authentication
  - Per-token credit billing with configurable per-model pricing
  - Rate limiting (RPM + TPM)
  - Usage analytics and transaction history

AIClient-2-API handles:
  - Protocol transformation (Gemini CLI, Antigravity, Kiro → OpenAI format)
  - Account pool rotation with LRU scoring and health checks
  - Automatic fallback chains between provider types
  - OAuth credential management and token refresh

Architecture:
  User → This Gateway (auth, billing, rate limit) → AIClient-2-API (transform, rotate) → Providers
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from proxy import proxy


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    # Startup
    print("🚀 AI Inference Gateway starting...")
    print(f"   → AIClient-2-API backend: {proxy.base_url}")
    yield
    # Shutdown
    await proxy.close()
    print("👋 AI Inference Gateway stopped.")


app = FastAPI(
    title="AI Inference Gateway",
    description=(
        "OpenAI-compatible API gateway with per-token billing. "
        "Routes through Gemini CLI, Antigravity, Kiro, and traditional API providers."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# CORS for dashboard
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -- Mount routes --
from routes_chat import router as chat_router
from routes_native import router as native_router
from routes_users import router as users_router
from routes_admin import router as admin_router

app.include_router(chat_router, tags=["Inference"])
app.include_router(native_router, tags=["Native Protocols"])
app.include_router(users_router, prefix="/api", tags=["Users & Billing"])
app.include_router(admin_router, prefix="/api", tags=["Admin"])


# -- Health check --
@app.get("/health")
async def health():
    return {"status": "healthy", "service": "ai-inference-gateway"}


@app.get("/")
async def root():
    return {
        "service": "AI Inference Gateway",
        "version": "1.0.0",
        "docs": "/docs",
        "endpoints": {
            "chat": "POST /v1/chat/completions",
            "models": "GET /v1/models",
            "register": "POST /api/auth/register",
            "login": "POST /api/auth/login",
            "usage": "GET /api/user/usage",
            "pricing": "GET /api/pricing",
        },
    }


# -- Global error handler --
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    return JSONResponse(
        status_code=500,
        content={
            "error": "internal_server_error",
            "message": "An unexpected error occurred. Please try again.",
        },
    )
