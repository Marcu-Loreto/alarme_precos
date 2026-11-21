import time
from datetime import date

import pytest

from alarme_precos.providers import (
    MockProvider,
    QuotaExceededError,
    SearchQuery,
    SerpApiProvider,
)
from alarme_precos.providers.serpapi import ACCOUNT_URL, SEARCH_URL
from alarme_precos.service import PriceService, QuotaService, build_provider

from .conftest import SAMPLE_ACCOUNT, SAMPLE_FLIGHTS, FakeResponse, FakeSession

QUERY = SearchQuery("GRU", "REC", date(2026, 12, 20))


def make_services(db, settings, account=SAMPLE_ACCOUNT):
    session = FakeSession(
        {SEARCH_URL: FakeResponse(200, SAMPLE_FLIGHTS), ACCOUNT_URL: FakeResponse(200, account)}
    )

    def factory(s):
        if not s.has_api_key:
            return MockProvider()
        return SerpApiProvider(s.serpapi_api_key, session=session)

    quota = QuotaService(db, settings_fn=lambda: settings, provider_factory=factory)
    prices = PriceService(db, quota, settings_fn=lambda: settings, provider_factory=factory)
    return prices, quota, session


def test_build_provider_uses_env_key(settings, demo_settings):
    assert isinstance(build_provider(settings), SerpApiProvider)
    assert isinstance(build_provider(demo_settings), MockProvider)


def test_cache_avoids_second_api_call(db, settings):
    prices, _, session = make_services(db, settings)
    first = prices.search(QUERY)
    second = prices.search(QUERY)

    assert not first.from_cache and second.from_cache
    assert len([c for c in session.calls if c[0] == SEARCH_URL]) == 1
    assert db.count_api_calls(0) == 1
    assert db.count_cache_hits(0) == 1


def test_demo_mode_never_calls_api(db, demo_settings):
    prices, _, session = make_services(db, demo_settings)
    result = prices.search(QUERY)
    assert result.is_demo and result.offers
    assert session.calls == []


def test_hourly_guard_blocks(db, settings):
    from dataclasses import replace

    prices, _, _ = make_services(db, replace(settings, hourly_limit=1))
    prices.search(QUERY)
    with pytest.raises(QuotaExceededError, match="por hora"):
        prices.search(QUERY, use_cache=False)


def test_exhausted_quota_blocks_after_account_read(db, settings):
    prices, quota, session = make_services(db, settings, {**SAMPLE_ACCOUNT, "total_searches_left": 0})
    quota.status()
    with pytest.raises(QuotaExceededError, match="cota"):
        prices.search(QUERY)
    assert not [c for c in session.calls if c[0] == SEARCH_URL]


def test_quota_status_free_plan(db, settings):
    prices, quota, _ = make_services(db, settings)
    prices.search(QUERY)
    db.execute(
        "INSERT INTO monitors (origin, destination, outbound_date, target_price, interval_hours, created_at) "
        "VALUES ('GRU','REC','2026-12-20',500,6,?)",
        (time.time(),),
    )
    st = quota.status()
    assert st.mode == "serpapi"
    assert st.is_free_plan is True
    assert st.this_month_usage == 12 and st.searches_per_month == 250
    assert st.usage_percent == pytest.approx(4.8)
    assert st.local_calls_month == 1
    assert st.monitors_projection == 120


def test_quota_status_paid_plan(db, settings):
    paid = {**SAMPLE_ACCOUNT, "plan_id": "developer", "plan_name": "Developer Plan", "searches_per_month": 5000}
    _, quota, _ = make_services(db, settings, paid)
    assert quota.status().is_free_plan is False


def test_account_is_cached(db, settings):
    _, quota, session = make_services(db, settings)
    quota.status()
    quota.status()
    assert len([c for c in session.calls if c[0] == ACCOUNT_URL]) == 1
    quota.status(force=True)
    assert len([c for c in session.calls if c[0] == ACCOUNT_URL]) == 2


def test_demo_quota_status(db, demo_settings):
    _, quota, session = make_services(db, demo_settings)
    assert quota.status().mode == "demo"
    assert session.calls == []
