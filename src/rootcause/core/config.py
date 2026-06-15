from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # LLM API keys
    openai_api_key: str = Field(default="", description="OpenAI API key")
    anthropic_api_key: str = Field(default="", description="Anthropic API key")
    cohere_api_key: str = Field(default="", description="Cohere API key for reranking")

    # PostgreSQL
    database_url: str = Field(
        default="postgresql+asyncpg://postgres:password@localhost:5432/rootcause"
    )

    @field_validator("database_url", mode="before")
    @classmethod
    def ensure_asyncpg_scheme(cls, v: str) -> str:
        """Render injects postgresql:// URLs — rewrite to asyncpg scheme."""
        if isinstance(v, str) and v.startswith("postgresql://"):
            return v.replace("postgresql://", "postgresql+asyncpg://", 1)
        return v

    # Redis
    redis_url: str = Field(default="redis://localhost:6379")

    # Qdrant
    qdrant_host: str = Field(default="localhost")
    qdrant_port: int = Field(default=6333)
    qdrant_collection: str = Field(default="rootcause_runbooks")

    # Neo4j
    neo4j_uri: str = Field(default="bolt://localhost:7687")
    neo4j_user: str = Field(default="neo4j")
    neo4j_password: str = Field(default="password")

    # Langfuse observability
    langfuse_public_key: str = Field(default="")
    langfuse_secret_key: str = Field(default="")
    langfuse_host: str = Field(default="https://cloud.langfuse.com")

    # Model routing
    model_triage: str = Field(default="gpt-4o-mini")
    model_agents: str = Field(default="gpt-4o-mini")
    model_rca: str = Field(default="claude-haiku-4-5-20251001")

    # CORS — comma-separated list of allowed origins in production
    cors_origins: str = Field(default="*", description="Comma-separated allowed origins, or * for all")

    # Authentication — leave empty to disable (development default)
    api_secret_key: str = Field(default="", description="Bearer token required on /incidents/* routes")

    # Application
    app_env: str = Field(default="development")
    log_level: str = Field(default="INFO")


@lru_cache
def get_settings() -> Settings:
    return Settings()
