"""Backend configuration.

There is no default production credential anywhere in this file. If the deployment
does not supply API keys, the service starts in an explicitly labelled development
mode with development keys, and says so on /ready.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from dms.domain.enums import Role


def _split(value: str) -> list[str]:
    return [v.strip() for v in value.split(",") if v.strip()]


@dataclass
class Settings:
    database_url: str = field(
        default_factory=lambda: os.getenv("DMS_DATABASE_URL", "sqlite:///./dms_gateway.db")
    )
    environment: str = field(default_factory=lambda: os.getenv("DMS_ENV", "development"))
    cors_origins: list[str] = field(
        default_factory=lambda: _split(os.getenv("DMS_CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000,http://127.0.0.1:3000"))
    )
    max_upload_bytes: int = field(
        default_factory=lambda: int(os.getenv("DMS_MAX_UPLOAD_BYTES", str(8 * 1024 * 1024)))
    )
    page_size_default: int = 50
    page_size_max: int = 200
    ai_service_url: str | None = field(default_factory=lambda: os.getenv("DMS_AI_URL"))

    @property
    def is_production(self) -> bool:
        return self.environment.lower() in ("prod", "production")


settings = Settings()

#: Development identities. Real deployments supply DMS_API_KEYS and these are ignored.
DEV_API_KEYS: dict[str, tuple[str, Role, str]] = {
    "dev-reporter-key": ("user_reporter", Role.CITIZEN_REPORTER, "org_demo"),
    "dev-relay-key": ("user_relay", Role.VOLUNTEER_RELAY, "org_demo"),
    "dev-coordinator-key": ("user_coordinator", Role.EVENT_COORDINATOR, "org_demo"),
    "dev-medic-key": ("user_medic", Role.MEDICAL_RESPONDER, "org_demo"),
    "dev-authority-key": ("user_authority", Role.GOVERNMENT_AUTHORITY, "org_demo"),
    "dev-other-org-key": ("user_other", Role.EVENT_COORDINATOR, "org_other"),
}


def api_keys() -> dict[str, tuple[str, Role, str]]:
    """Parse DMS_API_KEYS as ``key:user:ROLE:org`` entries, comma separated."""
    raw = os.getenv("DMS_API_KEYS", "")
    if not raw:
        if settings.is_production:
            return {}  # fail closed: production with no keys authorizes nobody
        return dict(DEV_API_KEYS)
    parsed: dict[str, tuple[str, Role, str]] = {}
    for entry in _split(raw):
        parts = entry.split(":")
        if len(parts) != 4:
            continue
        key, user, role, org = parts
        try:
            parsed[key] = (user, Role(role), org)
        except ValueError:
            continue
    return parsed
