"""Runtime settings. Everything comes from env vars; see .env.example."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from enum import StrEnum


class Mode(StrEnum):
    DRY_RUN = "dry_run"
    LIVE = "live"


@dataclass(frozen=True)
class Settings:
    mode: Mode = field(default_factory=lambda: Mode(os.environ.get("CMP_MODE", "dry_run")))
    database_url: str = field(
        default_factory=lambda: os.environ.get("CMP_DATABASE_URL", "sqlite:///cmp.db")
    )
    timezone: str = field(
        default_factory=lambda: os.environ.get("CMP_TIMEZONE", "Australia/Sydney")
    )
    use_fixtures: bool = field(default_factory=lambda: os.environ.get("CMP_FIXTURES") == "1")
    af_api_token: str = field(default_factory=lambda: os.environ.get("AF_API_TOKEN", ""))
    asa_client_id: str = field(default_factory=lambda: os.environ.get("ASA_CLIENT_ID", ""))
    asa_team_id: str = field(default_factory=lambda: os.environ.get("ASA_TEAM_ID", ""))
    asa_key_id: str = field(default_factory=lambda: os.environ.get("ASA_KEY_ID", ""))
    asa_private_key_path: str = field(
        default_factory=lambda: os.environ.get("ASA_PRIVATE_KEY_PATH", "secrets/private-key.pem")
    )

    @property
    def is_live(self) -> bool:
        return self.mode is Mode.LIVE


def get_settings() -> Settings:
    return Settings()
