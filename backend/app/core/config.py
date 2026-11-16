from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "AI Meeting Workspace"
    app_version: str = "0.1.0"
    database_url: str = "postgresql+psycopg://meeting_user:meeting_password@localhost:5432/meeting_workspace"
    jwt_secret_key: str = "change-this-to-a-long-random-secret"
    redis_url: str = "redis://localhost:6379/0"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 43200  # 30 days

    # LLM & AI configurations
    openai_api_key: str | None = None
    gemini_api_key: str | None = None
    hf_token: str | None = None
    llm_provider: str = "auto"  # "auto", "gemini", "openai"
    llm_model: str = "gemini-1.5-flash"
    openai_model: str = "gpt-4o-mini"
    embedding_model: str = "text-embedding-004"

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )


settings = Settings()
