"""
Configuration settings for the AI Inference Gateway.
"""
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://inference:changeme@localhost:5432/inference_gateway"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # AIClient-2-API upstream
    AICLIENT2API_BASE_URL: str = "http://localhost:3001"
    AICLIENT2API_KEY: str = "123456"

    # Antigravity-2-API upstream (specialized for Antigravity/Gemini)
    ANTIGRAVITY2API_BASE_URL: str = "http://localhost:8045"
    ANTIGRAVITY2API_KEY: str = "123456"


    # WebAI2API upstream (specialized for Trae/MarsCode browser automation)
    WEBAI2API_BASE_URL: str = "http://localhost:3002"
    WEBAI2API_KEY: str = "sk-webai-default-key-123"

    # GitHub Models (free tier; requires a GitHub PAT with models:read scope)
    # Generate at https://github.com/settings/tokens
    GITHUB_TOKEN: str = ""

    # Copilot-API (ericc-ch/copilot-api) — GitHub Copilot → OpenAI/Anthropic proxy
    # No API key needed: the container authenticates via GitHub OAuth on first start.
    # Run: docker exec -it copilot-api npx copilot-api start (then follow the auth link)
    COPILOT_API_BASE_URL: str = "http://localhost:4141"

    # Stripe (optional)
    STRIPE_SECRET_KEY: Optional[str] = None
    STRIPE_WEBHOOK_SECRET: Optional[str] = None

    # Auth
    MASTER_API_KEY: str = "sk-master-change-me"
    JWT_SECRET: str = "change-this-secret-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRY_HOURS: int = 24

    # Rate limiting defaults
    DEFAULT_RPM: int = 60       # requests per minute
    DEFAULT_TPM: int = 100000   # tokens per minute

    # Free credits for new users (in micro-credits; 10M = 10 credits)
    NEW_USER_FREE_CREDITS: int = 10_000_000

    # Provider route preferences (tried in this order for "auto" model)
    PROVIDER_PRIORITY: list = [
        "gemini-cli-oauth",
        "gemini-antigravity",
        "claude-kiro-oauth",
        "openai-qwen-oauth",
        "openai-custom",
        "claude-custom",
    ]

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
