"""Application configuration using Pydantic Settings."""

from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # App
    APP_NAME: str = "B2B Sales Pipeline"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    CORS_ORIGINS: list[str] = []
    ENABLE_SCRAPING: bool = True
    B2B_BOOTSTRAP_EMAIL: str = ""
    B2B_BOOTSTRAP_PASSWORD: Optional[SecretStr] = None
    SECRET_KEY: str = Field(..., description="Secret key for JWT tokens")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30 * 24 * 60  # 30 days

    # Database
    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/b2b_sales",
        description="PostgreSQL async connection string",
    )
    DATABASE_POOL_SIZE: int = 10
    DATABASE_MAX_OVERFLOW: int = 20

    # Redis
    REDIS_URL: str = Field(
        default="redis://localhost:6379/0",
        description="Redis connection for Celery and caching",
    )

    # Celery
    CELERY_BROKER_URL: str = Field(default="redis://localhost:6379/1")
    CELERY_RESULT_BACKEND: str = Field(default="redis://localhost:6379/2")

    # Email (SMTP)
    SMTP_HOST: str = "smtp.office365.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = ""
    SMTP_USE_TLS: bool = True

    # Zalo OA
    ZOA_APP_ID: str = ""
    ZOA_SECRET_KEY: str = ""
    ZOA_ACCESS_TOKEN: str = ""
    ZOA_REFRESH_TOKEN: str = ""

    # LinkedIn
    LINKEDIN_CLIENT_ID: str = ""
    LINKEDIN_CLIENT_SECRET: str = ""
    LINKEDIN_REDIRECT_URI: str = ""

    # Apollo.io
    APOLLO_API_KEY: str = ""
    APOLLO_BASE_URL: str = "https://api.apollo.io/v1"

    # AI / LLM
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o-mini"
    OPENAI_MAX_TOKENS: int = 2000
    OPENAI_TEMPERATURE: float = 0.7

    # Anthropic (backup)
    ANTHROPIC_API_KEY: str = ""
    ANTHROPIC_MODEL: str = "claude-3-haiku-20240307"

    # Scraping
    SCRAPER_DELAY_MIN: float = 2.0
    SCRAPER_DELAY_MAX: float = 5.0
    SCRAPER_TIMEOUT: int = 30
    SCRAPER_MAX_RETRIES: int = 3
    PLAYWRIGHT_HEADLESS: bool = True
    PLAYWRIGHT_EXECUTABLE_PATH: Optional[str] = None

    # Outreach
    OUTREACH_DAILY_LIMIT: int = 30
    OUTREACH_DELAY_MIN: float = 8.0
    OUTREACH_DELAY_MAX: float = 15.0
    OUTREACH_FOLLOWUP_DAYS: int = 3
    OUTREACH_MAX_FOLLOWUPS: int = 3

    # Zalo OA
    ZALO_OA_ID: str = ""
    ZALO_OA_SECRET: str = ""

    # LinkedIn Automation
    LINKEDIN_AUTOMATION_ENABLED: bool = False

    # Monitoring
    SENTRY_DSN: str = ""
    LOG_LEVEL: str = "INFO"

    # File storage
    UPLOAD_DIR: Path = Path("./uploads")
    MAX_FILE_SIZE: int = 10 * 1024 * 1024  # 10MB

    @property
    def database_url_sync(self) -> str:
        """Sync version of DATABASE_URL for Alembic."""
        return self.DATABASE_URL.replace("postgresql+asyncpg", "postgresql")


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


settings = get_settings()
