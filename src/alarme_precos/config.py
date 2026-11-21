"""Configuração lida do arquivo .env.

O .env é relido a cada chamada de ``get_settings()``. Assim, quando o admin
troca a ``SERPAPI_API_KEY`` (por exemplo, ao contratar um plano pago), o
sistema passa a usar a nova chave na próxima busca, sem mexer no código e sem
reiniciar o app.

Precedência: valores do arquivo .env > variáveis de ambiente > padrões.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import dotenv_values

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _env_file() -> Path:
    return Path(os.environ.get("ALARME_ENV_FILE", PROJECT_ROOT / ".env"))


def _as_bool(value: str | None, default: bool = False) -> bool:
    if value is None or value == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "sim", "on"}


def _as_int(value: str | None, default: int) -> int:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return default


def _as_float(value: str | None, default: float) -> float:
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return default


@dataclass(frozen=True)
class Settings:
    serpapi_api_key: str | None
    currency: str
    language: str
    country: str
    cache_ttl_minutes: int
    monitor_interval_hours: float
    free_plan_searches: int
    hourly_limit: int
    db_path: Path
    share: bool
    auth_user: str | None
    auth_password: str | None
    server_name: str
    server_port: int

    @property
    def has_api_key(self) -> bool:
        return bool(self.serpapi_api_key)

    @property
    def auth(self) -> tuple[str, str] | None:
        if self.auth_user and self.auth_password:
            return (self.auth_user, self.auth_password)
        return None


def get_settings() -> Settings:
    file_values = {k: v for k, v in dotenv_values(_env_file()).items() if v is not None}
    values = {**os.environ, **file_values}

    def get(name: str, default: str | None = None) -> str | None:
        raw = values.get(name)
        if raw is None or raw.strip() == "":
            return default
        return raw.strip()

    db_path = Path(get("ALARME_DB_PATH", str(PROJECT_ROOT / "data" / "alarme_precos.db")))

    return Settings(
        serpapi_api_key=get("SERPAPI_API_KEY"),
        currency=get("ALARME_CURRENCY", "BRL"),
        language=get("ALARME_LANGUAGE", "pt"),
        country=get("ALARME_COUNTRY", "br"),
        cache_ttl_minutes=max(0, _as_int(get("ALARME_CACHE_TTL_MINUTES"), 60)),
        monitor_interval_hours=max(1.0, _as_float(get("ALARME_MONITOR_INTERVAL_HOURS"), 6.0)),
        free_plan_searches=_as_int(get("SERPAPI_FREE_PLAN_SEARCHES"), 250),
        hourly_limit=max(1, _as_int(get("SERPAPI_HOURLY_LIMIT"), 50)),
        db_path=db_path,
        share=_as_bool(get("GRADIO_SHARE"), False),
        auth_user=get("APP_AUTH_USER"),
        auth_password=get("APP_AUTH_PASSWORD"),
        server_name=get("GRADIO_SERVER_NAME", "127.0.0.1"),
        server_port=_as_int(get("GRADIO_SERVER_PORT"), 7860),
    )
