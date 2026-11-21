from datetime import date

import pytest

from alarme_precos.providers import (
    ProviderError,
    QuotaExceededError,
    SearchQuery,
    SerpApiProvider,
)
from alarme_precos.providers.serpapi import ACCOUNT_URL, SEARCH_URL

from .conftest import SAMPLE_ACCOUNT, SAMPLE_FLIGHTS, FakeResponse, FakeSession

QUERY = SearchQuery("GRU", "REC", date(2026, 12, 20))


def provider(responses):
    session = FakeSession(responses)
    return SerpApiProvider("k", session=session), session


def test_search_parses_offers_sorted_by_price():
    p, _ = provider({SEARCH_URL: FakeResponse(200, SAMPLE_FLIGHTS)})
    result = p.search(QUERY)

    assert [o.price for o in result.offers] == [480.0, 612.0]  # sem preço foi ignorado
    gol = result.offers[0]
    assert gol.airline == "GOL"
    assert gol.stops == 1
    assert gol.departure_time == "2026-12-20 10:00"
    assert gol.arrival_time == "2026-12-20 15:30"
    assert gol.flight_numbers == "G3 1000, G3 1001"
    assert result.offers[1].is_best is True
    assert result.price_insights["price_level"] == "low"
    assert not result.is_demo


def test_search_sends_expected_params():
    p, session = provider({SEARCH_URL: FakeResponse(200, SAMPLE_FLIGHTS)})
    p.search(QUERY)
    _, params = session.calls[0]
    assert params["engine"] == "google_flights"
    assert params["departure_id"] == "GRU"
    assert params["arrival_id"] == "REC"
    assert params["outbound_date"] == "2026-12-20"
    assert params["type"] == 2
    assert params["currency"] == "BRL"


def test_no_results_is_empty_not_error():
    p, _ = provider({SEARCH_URL: FakeResponse(200, {"error": "Google hasn't returned any results for this query."})})
    assert p.search(QUERY).offers == []


@pytest.mark.parametrize(
    "status,exc,text",
    [(401, ProviderError, "inválida"), (429, QuotaExceededError, "cota"), (403, ProviderError, "permissão")],
)
def test_http_errors(status, exc, text):
    p, _ = provider({SEARCH_URL: FakeResponse(status, {"error": "x"})})
    with pytest.raises(exc, match=text):
        p.search(QUERY)


@pytest.mark.parametrize("status", [401, 429, 500])
def test_error_message_does_not_leak_api_key(status):
    session = FakeSession({SEARCH_URL: FakeResponse(status, None)})
    p = SerpApiProvider("SECRET-KEY-123", session=session)
    with pytest.raises(ProviderError) as info:
        p.search(QUERY)
    assert "SECRET-KEY-123" not in str(info.value)


def test_fetch_account():
    p, session = provider({ACCOUNT_URL: FakeResponse(200, SAMPLE_ACCOUNT)})
    assert p.fetch_account()["plan_name"] == "Free Plan"
    assert session.calls[0][0] == ACCOUNT_URL
