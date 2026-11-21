from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from alarme_precos.config import Settings
from alarme_precos.storage import Database


class FakeResponse:
    def __init__(self, status_code: int, payload: dict | None = None):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        if self._payload is None:
            raise ValueError("no json")
        return self._payload


class FakeSession:
    """Substitui requests.Session: devolve respostas por URL e registra chamadas."""

    def __init__(self, responses: dict[str, FakeResponse]):
        self.responses = responses
        self.calls: list[tuple[str, dict]] = []

    def get(self, url, params=None, timeout=None):
        assert timeout is not None, "toda chamada HTTP precisa de timeout"
        self.calls.append((url, dict(params or {})))
        return self.responses[url]


SAMPLE_FLIGHTS = {
    "search_metadata": {"id": "abc", "status": "Success"},
    "best_flights": [
        {
            "flights": [
                {
                    "departure_airport": {"name": "Guarulhos", "id": "GRU", "time": "2026-12-20 06:00"},
                    "arrival_airport": {"name": "Recife", "id": "REC", "time": "2026-12-20 09:10"},
                    "airline": "LATAM",
                    "flight_number": "LA 3400",
                    "duration": 190,
                }
            ],
            "total_duration": 190,
            "price": 612,
            "type": "One way",
        }
    ],
    "other_flights": [
        {
            "flights": [
                {
                    "departure_airport": {"id": "GRU", "time": "2026-12-20 10:00"},
                    "arrival_airport": {"id": "BSB", "time": "2026-12-20 11:40"},
                    "airline": "GOL",
                    "flight_number": "G3 1000",
                },
                {
                    "departure_airport": {"id": "BSB", "time": "2026-12-20 13:00"},
                    "arrival_airport": {"id": "REC", "time": "2026-12-20 15:30"},
                    "airline": "GOL",
                    "flight_number": "G3 1001",
                },
            ],
            "layovers": [{"duration": 80, "name": "Brasília", "id": "BSB"}],
            "total_duration": 330,
            "price": 480,
        },
        {"flights": [{"airline": "Azul"}], "total_duration": 200},  # sem preço: ignorado
    ],
    "price_insights": {"lowest_price": 480, "price_level": "low", "typical_price_range": [550, 900]},
}

SAMPLE_ACCOUNT = {
    "plan_id": "free",
    "plan_name": "Free Plan",
    "searches_per_month": 250,
    "plan_searches_left": 238,
    "extra_credits": 0,
    "total_searches_left": 238,
    "this_month_usage": 12,
    "this_hour_searches": 2,
    "account_rate_limit_per_hour": 50,
    "plan_renewal_date": None,
}


@pytest.fixture
def db() -> Database:
    return Database(":memory:")


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        serpapi_api_key="test-key",
        currency="BRL",
        language="pt",
        country="br",
        cache_ttl_minutes=60,
        monitor_interval_hours=6,
        free_plan_searches=250,
        hourly_limit=50,
        db_path=tmp_path / "t.db",
        share=False,
        auth_user=None,
        auth_password=None,
        server_name="127.0.0.1",
        server_port=7860,
    )


@pytest.fixture
def demo_settings(settings: Settings) -> Settings:
    return replace(settings, serpapi_api_key=None)

# Formato real devolvido pelo SerpApi (consulta de 21/11/2026, post_data encurtado)
SAMPLE_BOOKING = {
    "search_metadata": {"id": "x", "status": "Success"},
    "selected_flights": [],
    "booking_options": [
        {
            "together": {
                "book_with": "LATAM",
                "airline": True,
                "marketed_as": ["LA 4554"],
                "price": 1620,
                "baggage_prices": ["1 free carry-on"],
                "booking_request": {"url": "https://www.google.com/travel/clk/f", "post_data": "u=..."},
            }
        },
        {
            "together": {
                "book_with": "Agência X",
                "airline": False,
                "marketed_as": ["LA 4554"],
                "price": 1580,
                "option_title": "Basic",
                "extensions": ["Sem reembolso"],
            }
        },
        {"separate_tickets": True, "departing": {"book_with": "Agência Y", "price": 1700}, "together": {}},
        {"together": {"book_with": "Sem preço"}},
    ],
}
