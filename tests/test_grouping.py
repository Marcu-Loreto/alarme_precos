from datetime import date

from alarme_precos.grouping import (
    by_airline,
    by_price,
    by_source,
    pick_offers_for_sources,
)
from alarme_precos.providers import (
    BookingOption,
    FlightOffer,
    MockProvider,
    SearchQuery,
    SerpApiProvider,
)
from alarme_precos.providers.serpapi import SEARCH_URL
from alarme_precos.service import PriceService, QuotaService

from .conftest import SAMPLE_BOOKING, SAMPLE_FLIGHTS, FakeResponse, FakeSession

QUERY = SearchQuery("GRU", "REC", date(2026, 12, 20))


def offer(airline, price, stops=0, duration=120, token="t"):
    return FlightOffer(airline, price, "2026-12-20 08:00", "2026-12-20 10:00", duration, stops, f"{airline[:2]} 1", False, token)


OFFERS = [offer("GOL", 700), offer("LATAM", 500, 1, 300), offer("Azul", 650), offer("LATAM", 900), offer("GOL", 480, 1)]


def test_by_price_sorted():
    df = by_price(OFFERS)
    assert list(df["Preço"]) == ["R$ 480,00", "R$ 500,00", "R$ 650,00", "R$ 700,00", "R$ 900,00"]
    assert list(df["#"]) == [1, 2, 3, 4, 5]
    assert df["Partida"][0] == "20-12-2026 08:00"


def test_by_airline_groups_and_orders_by_cheapest():
    summary, detail = by_airline(OFFERS)
    assert list(summary["Companhia"]) == ["GOL", "LATAM", "Azul"]
    gol = summary.iloc[0]
    assert gol["Ofertas"] == 2 and gol["Menor preço"] == "R$ 480,00" and gol["Preço médio"] == "R$ 590,00"
    assert gol["Voos diretos"] == 1
    assert list(detail["Companhia"]) == ["GOL", "GOL", "LATAM", "LATAM", "Azul"]
    assert list(detail["Preço"])[:2] == ["R$ 480,00", "R$ 700,00"]


def test_by_source_summary_and_diff_vs_airline():
    sources = {
        1: [BookingOption("LATAM", True, 500, "LA 1"), BookingOption("Agência X", False, 470, "LA 1")],
        4: [BookingOption("GOL", True, 480, "GO 1"), BookingOption("Agência X", False, 495, "GO 1")],
    }
    summary, detail = by_source(OFFERS, sources)
    assert list(summary["Fonte"]) == ["Agência X", "GOL", "LATAM"]
    ax = summary.iloc[0]
    assert ax["Tipo"] == "Agência" and ax["Voos vendidos"] == 2 and ax["Menor preço"] == "R$ 470,00"
    diffs = dict(zip(detail["Preço"], detail["vs. site da cia"]))
    assert diffs["R$ 470,00"] == "−R$ 30,00"
    assert diffs["R$ 495,00"] == "+R$ 15,00"
    assert diffs["R$ 500,00"] == "—"


def test_by_source_empty():
    summary, detail = by_source(OFFERS, {})
    assert summary.empty and detail.empty


def test_pick_offers_skips_done_and_tokenless():
    offers = [*OFFERS, offer("Copa", 100, token=None)]
    picked = pick_offers_for_sources(offers, {}, 3)
    assert [offers[i].price for i in picked] == [480, 500, 650]  # Copa sem token fica fora
    assert pick_offers_for_sources(offers, {picked[0]: []}, 3) == picked[1:]


# ------------------------------------------------------------ fontes reais
def test_parse_booking_options_real_format():
    session = FakeSession({SEARCH_URL: FakeResponse(200, SAMPLE_BOOKING)})
    p = SerpApiProvider("k", session=session)
    opts = p.booking_options(QUERY, offer("LATAM", 1620, token="TOKEN-1"))
    assert [(o.seller, o.price, o.is_airline) for o in opts] == [
        ("Agência X", 1580, False), ("LATAM", 1620, True), ("Agência Y", 1700, False),
    ]
    assert opts[1].baggage == "1 free carry-on" and opts[0].conditions == "Sem reembolso"
    assert session.calls[0][1]["booking_token"] == "TOKEN-1"


def test_offer_without_token_costs_nothing():
    session = FakeSession({})
    assert SerpApiProvider("k", session=session).booking_options(QUERY, offer("X", 1, token=None)) == []
    assert session.calls == []


def test_search_keeps_booking_token_and_google_url():
    data = {**SAMPLE_FLIGHTS, "search_metadata": {"google_flights_url": "https://www.google.com/travel/flights?x"}}
    data["best_flights"] = [{**data["best_flights"][0], "booking_token": "BT"}]
    p = SerpApiProvider("k", session=FakeSession({SEARCH_URL: FakeResponse(200, data)}))
    r = p.search(QUERY)
    assert any(o.booking_token == "BT" for o in r.offers)
    assert r.google_flights_url.startswith("https://www.google.com/travel/flights")


def test_service_caches_booking_options(db, settings):
    session = FakeSession({SEARCH_URL: FakeResponse(200, SAMPLE_BOOKING)})
    factory = lambda s: SerpApiProvider("k", session=session)
    quota = QuotaService(db, settings_fn=lambda: settings, provider_factory=factory)
    svc = PriceService(db, quota, settings_fn=lambda: settings, provider_factory=factory)
    o = offer("LATAM", 1620, token="TOKEN-1")
    first, second = svc.booking_options(QUERY, o), svc.booking_options(QUERY, o)
    assert [x.seller for x in first] == [x.seller for x in second]
    assert len(session.calls) == 1
    assert db.count_api_calls(0) == 1 and db.count_cache_hits(0) == 1


def test_mock_sources_are_marked_demo():
    opts = MockProvider().booking_options(QUERY, offer("LATAM", 500, token="demo-0"))
    assert opts and all("Demo" in o.seller or "demo" in o.seller for o in opts)
