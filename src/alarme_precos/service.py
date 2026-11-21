"""Serviços de busca (com cache e trava de cota) e de status da cota SerpApi."""

from __future__ import annotations

import hashlib
import logging
import threading
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import datetime

from .config import Settings, get_settings
from .providers import (
    BookingOption,
    FlightOffer,
    MockProvider,
    PriceProvider,
    ProviderError,
    QuotaExceededError,
    SearchQuery,
    SearchResult,
    SerpApiProvider,
)
from .storage import Database

log = logging.getLogger(__name__)

ACCOUNT_CACHE_SECONDS = 60


def build_provider(settings: Settings) -> PriceProvider:
    """Escolhe o provedor conforme o .env. Sem chave, cai no modo demonstração."""
    if settings.has_api_key:
        return SerpApiProvider(
            api_key=settings.serpapi_api_key or "",
            currency=settings.currency,
            language=settings.language,
            country=settings.country,
        )
    return MockProvider()


def _month_start(now: float) -> float:
    d = datetime.fromtimestamp(now)
    return d.replace(day=1, hour=0, minute=0, second=0, microsecond=0).timestamp()


def _day_start(now: float) -> float:
    d = datetime.fromtimestamp(now)
    return d.replace(hour=0, minute=0, second=0, microsecond=0).timestamp()


# --------------------------------------------------------------------- cota
@dataclass
class QuotaStatus:
    mode: str  # "demo" ou "serpapi"
    error: str | None = None
    plan_name: str | None = None
    plan_id: str | None = None
    is_free_plan: bool | None = None
    searches_per_month: int | None = None
    this_month_usage: int | None = None
    plan_searches_left: int | None = None
    extra_credits: int | None = None
    total_searches_left: int | None = None
    renewal_date: str | None = None
    rate_limit_per_hour: int | None = None
    this_hour_searches: int | None = None
    local_calls_today: int = 0
    local_calls_month: int = 0
    cache_hits_month: int = 0
    monitors_projection: int = 0
    fetched_at: float = field(default_factory=time.time)

    @property
    def usage_percent(self) -> float | None:
        if not self.searches_per_month or self.this_month_usage is None:
            return None
        return min(100.0, 100.0 * self.this_month_usage / self.searches_per_month)


class QuotaService:
    """Consulta a Account API do SerpApi (gratuita) e combina com o log local."""

    def __init__(
        self,
        db: Database,
        settings_fn: Callable[[], Settings] = get_settings,
        provider_factory: Callable[[Settings], PriceProvider] = build_provider,
    ):
        self.db = db
        self.settings_fn = settings_fn
        self.provider_factory = provider_factory
        self._lock = threading.Lock()
        self._cached: tuple[str, float, dict] | None = None  # (api_key, ts, account)

    def _account(self, settings: Settings, force: bool) -> dict:
        key = settings.serpapi_api_key or ""
        with self._lock:
            if (
                not force
                and self._cached
                and self._cached[0] == key
                and time.time() - self._cached[1] < ACCOUNT_CACHE_SECONDS
            ):
                return self._cached[2]
        provider = self.provider_factory(settings)
        if not isinstance(provider, SerpApiProvider):
            return {}
        account = provider.fetch_account()
        with self._lock:
            self._cached = (key, time.time(), account)
        return account

    def known_remaining(self) -> int | None:
        """Saldo da última consulta à conta (até 10 min atrás), sem nova chamada."""
        settings = self.settings_fn()
        with self._lock:
            if (
                self._cached
                and self._cached[0] == (settings.serpapi_api_key or "")
                and time.time() - self._cached[1] < 600
            ):
                value = self._cached[2].get("total_searches_left")
                return int(value) if value is not None else None
        return None

    def status(self, force: bool = False) -> QuotaStatus:
        settings = self.settings_fn()
        now = time.time()
        status = QuotaStatus(
            mode="serpapi" if settings.has_api_key else "demo",
            local_calls_today=self.db.count_api_calls(_day_start(now)),
            local_calls_month=self.db.count_api_calls(_month_start(now)),
            cache_hits_month=self.db.count_cache_hits(_month_start(now)),
            monitors_projection=self.monitors_projection(),
        )
        if not settings.has_api_key:
            return status
        try:
            acc = self._account(settings, force)
        except ProviderError as exc:
            status.error = str(exc)
            return status

        status.plan_name = acc.get("plan_name")
        status.plan_id = acc.get("plan_id")
        status.searches_per_month = acc.get("searches_per_month")
        status.this_month_usage = acc.get("this_month_usage")
        status.plan_searches_left = acc.get("plan_searches_left")
        status.extra_credits = acc.get("extra_credits")
        status.total_searches_left = acc.get("total_searches_left")
        status.renewal_date = acc.get("plan_renewal_date")
        status.rate_limit_per_hour = acc.get("account_rate_limit_per_hour")
        status.this_hour_searches = acc.get("this_hour_searches")
        plan_text = f"{status.plan_id or ''} {status.plan_name or ''}".lower()
        status.is_free_plan = "free" in plan_text or (
            status.searches_per_month is not None
            and status.searches_per_month <= settings.free_plan_searches
        )
        return status

    def monitors_projection(self) -> int:
        """Buscas/mês que os monitores ativos vão consumir (30 dias)."""
        rows = self.db.query("SELECT interval_hours FROM monitors WHERE active = 1")
        return int(sum(30 * 24 / max(1.0, r["interval_hours"]) for r in rows))


# -------------------------------------------------------------------- busca
class PriceService:
    def __init__(
        self,
        db: Database,
        quota: QuotaService,
        settings_fn: Callable[[], Settings] = get_settings,
        provider_factory: Callable[[Settings], PriceProvider] = build_provider,
    ):
        self.db = db
        self.quota = quota
        self.settings_fn = settings_fn
        self.provider_factory = provider_factory

    def search(self, query: SearchQuery, use_cache: bool = True) -> SearchResult:
        settings = self.settings_fn()
        provider = self.provider_factory(settings)

        if provider.is_demo:
            return provider.search(query)

        key = query.cache_key(provider.name, settings.currency)
        if use_cache:
            cached = self.db.cache_get(key, settings.cache_ttl_minutes * 60)
            if cached is not None:
                self.db.log_usage(provider.name, query.route, cached=True, success=True)
                return SearchResult.from_dict(cached, from_cache=True)

        self._guard_quota(provider.name, settings)

        try:
            result = provider.search(query)
        except ProviderError as exc:
            self.db.log_usage(provider.name, query.route, cached=False, success=False, error=str(exc))
            raise
        self.db.log_usage(provider.name, query.route, cached=False, success=True)
        self.db.cache_set(key, result.to_dict())
        return result

    def booking_options(self, query: SearchQuery, offer: FlightOffer) -> list[BookingOption]:
        """Fontes de venda de uma oferta (1 busca por oferta, com cache)."""
        settings = self.settings_fn()
        provider = self.provider_factory(settings)
        if provider.is_demo or not offer.booking_token:
            return provider.booking_options(query, offer)

        token_hash = hashlib.sha256(offer.booking_token.encode()).hexdigest()[:32]
        key = f"{provider.name}:booking:{settings.currency}:{token_hash}"
        route = f"{query.route} [fontes {offer.flight_numbers}]"
        cached = self.db.cache_get(key, settings.cache_ttl_minutes * 60)
        if cached is not None:
            self.db.log_usage(provider.name, route, cached=True, success=True)
            return [BookingOption(**o) for o in cached["options"]]

        self._guard_quota(provider.name, settings)
        try:
            options = provider.booking_options(query, offer)
        except ProviderError as exc:
            self.db.log_usage(provider.name, route, cached=False, success=False, error=str(exc))
            raise
        self.db.log_usage(provider.name, route, cached=False, success=True)
        self.db.cache_set(key, {"options": [asdict(o) for o in options]})
        return options

    def _guard_quota(self, provider_name: str, settings: Settings) -> None:
        last_hour = self.db.count_api_calls(time.time() - 3600, provider_name)
        if last_hour >= settings.hourly_limit:
            raise QuotaExceededError(
                f"Limite local de {settings.hourly_limit} buscas por hora atingido "
                "(SERPAPI_HOURLY_LIMIT). Aguarde alguns minutos."
            )
        remaining = self.quota.known_remaining()
        if remaining is not None and remaining <= 0:
            raise QuotaExceededError(
                "A cota do plano SerpApi acabou. Contrate um plano maior e troque a "
                "SERPAPI_API_KEY no .env, ou aguarde a renovação."
            )
