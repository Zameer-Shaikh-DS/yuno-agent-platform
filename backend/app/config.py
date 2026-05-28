from pathlib import Path
from functools import lru_cache
import os

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Project root (yuno-agent-platform/) — .env lives here, not in backend/
ROOT_DIR = Path(__file__).resolve().parents[2]
ENV_FILE = ROOT_DIR / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE) if ENV_FILE.exists() else None,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    xai_api_key: str = ""
    groq_api_key: str = ""
    xai_model: str = "grok-3-mini"
    groq_model: str = "llama-3.3-70b-versatile"
    llm_provider: str = ""  # auto | xai | groq
    database_url: str = "sqlite:///./yuno_agents.db"
    telegram_bot_token: str = ""
    telegram_default_agent_id: str = ""
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    mock_llm: bool = Field(default=False, validation_alias="MOCK_LLM")
    cors_origins: str = "http://localhost:5173,http://localhost:3000"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def llm_api_key(self) -> str:
        return self.groq_api_key or self.xai_api_key


@lru_cache
def get_settings() -> Settings:
    # Ensure root .env is loaded when cwd is backend/
    if ENV_FILE.exists():
        from dotenv import load_dotenv
        load_dotenv(ENV_FILE, override=False)

    s = Settings()
    if os.getenv("MOCK_LLM", "0").strip().lower() in ("1", "true", "yes"):
        s.mock_llm = True
    return s
