from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _ids(value: str | list[int] | None) -> list[int]:
    if value is None or value == "":
        return []
    if isinstance(value, list):
        return value
    return [int(x) for x in str(value).replace(" ", "").split(",") if x]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    telegram_bot_token: str = ""
    owner_telegram_ids: str = ""
    staff_telegram_ids: str = ""

    anthropic_api_key: str = ""
    claude_model: str = "claude-opus-5-5"
    claude_effort: str = "medium"
    claude_use_fallbacks: bool = True
    max_agent_iterations: int = 12

    database_url: str = "sqlite+aiosqlite:///./data/vtf.db"
    data_dir: Path = Path("./data")

    google_client_id: str = ""
    google_client_secret: str = ""
    google_refresh_token: str = ""
    google_calendar_id: str = "primary"
    google_drive_folder_id: str = ""

    auto_mail_enabled: bool = True
    mail_poll_seconds: int = 120
    max_revisions: int = 5
    reminder_interval_seconds: int = 60
    reminder_lead_hours: int = 24
    timezone: str = "Asia/Ho_Chi_Minh"

    @field_validator("data_dir", mode="before")
    @classmethod
    def _path(cls, v):
        return Path(v)

    @property
    def owner_ids(self) -> list[int]:
        return _ids(self.owner_telegram_ids)

    @property
    def staff_ids(self) -> list[int]:
        return _ids(self.staff_telegram_ids)

    @property
    def google_configured(self) -> bool:
        return bool(self.google_client_id and self.google_client_secret and self.google_refresh_token)


@lru_cache
def get_settings() -> Settings:
    return Settings()
