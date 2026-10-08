from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _load_dotenv(path: Path) -> None:
    """Load a minimal .env file without overwriting real environment variables."""
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        name = name.strip()
        if name and name not in os.environ:
            os.environ[name] = value.strip().strip('"').strip("'")


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int, minimum: int = 0) -> int:
    try:
        return max(minimum, int(os.getenv(name, str(default))))
    except ValueError:
        return default


def _env_float(name: str, default: float, minimum: float = 0.0) -> float:
    try:
        return max(minimum, float(os.getenv(name, str(default))))
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    api_key: str
    base_url: str
    cache_dir: Path
    cache_ttl_seconds: int
    request_timeout_seconds: float
    max_retries: int
    allow_stale_if_error: bool
    cors_origins: tuple[str, ...]
    report_sections: tuple[str, ...]
    max_missing_feature_rate: float
    min_valid_peers: int
    cors_origin_regex: str | None = r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$"
    request_min_interval_seconds: float = 2.1

    @classmethod
    def from_env(cls) -> "Settings":
        _load_dotenv(PROJECT_ROOT / ".env")
        origins = tuple(
            item.strip()
            for item in os.getenv(
                "CORS_ORIGINS", "http://localhost:5173,http://localhost:3000"
            ).split(",")
            if item.strip()
        )
        # Only the five sections used by the 15-feature engine are requested.
        sections = tuple(
            item.strip()
            for item in os.getenv(
                "SECTORS_REPORT_SECTIONS",
                "overview,valuation,financials,dividend,peers",
            ).split(",")
            if item.strip()
        )
        api_key = os.getenv("SECTORS_API_KEY", "").strip()
        # Docs require the raw key in Authorization. Accepting a pasted
        # ``Bearer ...`` form avoids a common 401 without logging the secret.
        if api_key.lower().startswith("bearer "):
            api_key = api_key[7:].strip()
        return cls(
            api_key=api_key,
            base_url=os.getenv("SECTORS_BASE_URL", "https://api.sectors.app/v2").rstrip("/"),
            cache_dir=Path(
                os.getenv("SECTORS_CACHE_DIR", str(PROJECT_ROOT / "data" / "cache"))
            ).resolve(),
            cache_ttl_seconds=_env_int("SECTORS_CACHE_TTL_SECONDS", 604_800, 60),
            request_timeout_seconds=_env_float("SECTORS_REQUEST_TIMEOUT_SECONDS", 30.0, 1.0),
            # Default zero: do not surprise the user with repeated credit-consuming calls.
            max_retries=_env_int("SECTORS_MAX_RETRIES", 0, 0),
            allow_stale_if_error=_env_bool("SECTORS_ALLOW_STALE_IF_ERROR", True),
            cors_origins=origins,
            report_sections=sections,
            max_missing_feature_rate=_env_float(
                "MAX_MISSING_FEATURE_RATE", 0.35, 0.0
            ),
            min_valid_peers=_env_int("MIN_VALID_PEERS", 5, 1),
            cors_origin_regex=os.getenv(
                "CORS_ORIGIN_REGEX",
                r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
            ).strip()
            or None,
            request_min_interval_seconds=_env_float(
                "SECTORS_REQUEST_MIN_INTERVAL_SECONDS", 2.1, 0.0
            ),
        )


settings = Settings.from_env()
