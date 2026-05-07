"""Path constants + runtime settings loaded from .env."""

from __future__ import annotations

from pathlib import Path

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DATA_ROOT = REPO_ROOT / "data"

_DEFAULT_LLM_BASE_URL = "https://api.openai.com/v1"
_DEFAULT_LLM_MODEL = "gpt-4o-mini"


def resolve_data_root(value: str | Path | None = None) -> Path:
    if value is None or str(value).strip() == "":
        return DEFAULT_DATA_ROOT
    return Path(value)


class Settings(BaseSettings):
    """Runtime settings. Loaded from .env at the repo root and overridable by env vars."""

    model_config = SettingsConfigDict(
        env_file=str(REPO_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    neo4j_uri: str = "neo4j://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = ""
    neo4j_database: str = "neo4j"

    # LLM_* is the recommended env prefix; AGENT_* remains supported (same fields).
    agent_base_url: str = Field(
        default=_DEFAULT_LLM_BASE_URL,
        validation_alias=AliasChoices("LLM_BASE_URL", "AGENT_BASE_URL"),
    )
    agent_model: str = Field(
        default=_DEFAULT_LLM_MODEL,
        validation_alias=AliasChoices("LLM_MODEL", "AGENT_MODEL"),
    )
    agent_api_key: str = Field(
        default="",
        validation_alias=AliasChoices("LLM_API_KEY", "AGENT_API_KEY"),
    )
    agent_timeout_seconds: float = Field(
        default=30.0,
        validation_alias=AliasChoices("LLM_TIMEOUT_SECONDS", "AGENT_TIMEOUT_SECONDS"),
    )
    agent_max_concurrency: int = Field(
        default=32,
        ge=1,
        validation_alias=AliasChoices("LLM_MAX_CONCURRENCY", "AGENT_MAX_CONCURRENCY"),
    )

    embedding_model: str = "intfloat/e5-small-v2"

    data_root: Path = DEFAULT_DATA_ROOT

    @field_validator("agent_base_url", mode="before")
    @classmethod
    def _default_base_url_when_blank(cls, value: object) -> object:
        if isinstance(value, str) and value.strip() == "":
            return _DEFAULT_LLM_BASE_URL
        return value

    @field_validator("agent_model", mode="before")
    @classmethod
    def _default_model_when_blank(cls, value: object) -> object:
        if isinstance(value, str) and value.strip() == "":
            return _DEFAULT_LLM_MODEL
        return value
