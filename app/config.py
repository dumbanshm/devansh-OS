"""Application configuration, loaded from environment / .env.

Everything is optional so the app always boots. A provider that lacks its
credentials reports itself as disabled rather than crashing the dashboard.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from zoneinfo import ZoneInfo

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
WEB_DIR = BASE_DIR / "web"
MIGRATIONS_DIR = BASE_DIR / "migrations"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Providers
    github_token: str = ""
    github_username: str = ""
    leetcode_username: str = ""
    # Directory holding Claude Code session logs (the `projects/` folder).
    # Defaults to ~/.claude/projects; override with CLAUDE_DIR (e.g. a mount
    # path inside Docker).
    claude_dir: str = str(Path.home() / ".claude" / "projects")
    # Path to a Hevy CSV export (or a folder of them — newest is used). Empty
    # → look for data/hevy.csv. Drop your export there and the Gym provider
    # lights up; no Hevy Pro / API key needed.
    hevy_csv: str = ""

    # Scheduling / locale
    poll_minutes: int = 30
    timezone: str = "UTC"

    # Server
    host: str = "127.0.0.1"
    port: int = 8000

    @property
    def db_path(self) -> Path:
        return DATA_DIR / "devansh.db"

    @property
    def tz(self) -> ZoneInfo:
        try:
            return ZoneInfo(self.timezone)
        except Exception:
            return ZoneInfo("UTC")


@lru_cache
def get_settings() -> Settings:
    return Settings()
