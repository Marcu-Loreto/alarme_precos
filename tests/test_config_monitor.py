from datetime import date, timedelta

import pytest

from alarme_precos.airports import parse_future_date, parse_iata
from alarme_precos.config import get_settings
from alarme_precos.fmt import br_date, br_datetime
from alarme_precos.monitor import MonitorService
from alarme_precos.providers import FlightOffer, SearchResult


# ------------------------------------------------------------------ config
def test_env_file_change_is_picked_up_without_restart(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    monkeypatch.setenv("ALARME_ENV_FILE", str(env))
    monkeypatch.delenv("SERPAPI_API_KEY", raising=False)

    env.write_text("SERPAPI_API_KEY=\n")
    assert get_settings().has_api_key is False

    env.write_text("SERPAPI_API_KEY=chave-plano-pago\n")
    assert get_settings().serpapi_api_key == "chave-plano-pago"


def test_defaults(tmp_path, monkeypatch):
    monkeypatch.setenv("ALARME_ENV_FILE", str(tmp_path / "nao-existe.env"))
    for var in ("SERPAPI_API_KEY", "GRADIO_SHARE", "ALARME_MONITOR_INTERVAL_HOURS"):
        monkeypatch.delenv(var, raising=False)
    s = get_settings()
    assert s.share is False
    assert s.monitor_interval_hours == 6
    assert s.currency == "BRL"


# ---------------------------------------------------------------- airports
@pytest.mark.parametrize("raw", ["GRU", "gru", " GRU — São Paulo (Guarulhos)"])
def test_parse_iata_ok(raw):
    assert parse_iata(raw) == "GRU"


@pytest.mark.parametrize("raw", ["", "São Paulo", "GR", "G1U"])
def test_parse_iata_invalid(raw):
    with pytest.raises(ValueError):
        parse_iata(raw)


@pytest.mark.parametrize("raw", ["20-12-2026", "20/12/2026", " 20-12-2026 ", "2026-12-20"])
def test_parse_date_br(raw):
    assert parse_future_date(raw, date(2026, 11, 21)) == date(2026, 12, 20)


@pytest.mark.parametrize("raw", ["01-11-2026", "amanhã", "12-20-2026", "32-12-2026", ""])
def test_parse_date_invalid(raw):
    with pytest.raises(ValueError):
        parse_future_date(raw, date(2026, 11, 21))


def test_parse_date_error_mentions_br_format():
    with pytest.raises(ValueError, match="DD-MM-AAAA"):
        parse_future_date("xx", date(2026, 11, 21))


def test_br_formatting():
    assert br_date(date(2026, 12, 5)) == "05-12-2026"
    assert br_date("2026-12-05") == "05-12-2026"
    assert br_date(None) == "—"
    assert br_datetime("2026-12-20 06:00") == "20-12-2026 06:00"
    assert br_datetime("") == "—"


# ----------------------------------------------------------------- monitor
class FakePrices:
    def __init__(self, prices):
        self.prices = list(prices)
        self.calls = 0

    def search(self, query, use_cache=True):
        self.calls += 1
        price = self.prices.pop(0)
        return SearchResult("serpapi", [FlightOffer("LATAM", price, "", "", 100, 0, "LA 1")])


def test_monitor_alerts_only_on_new_low(db):
    fake = FakePrices([700, 450, 460, 430, 800, 440])
    mon = MonitorService(db, fake)
    future = date.today() + timedelta(days=30)
    mon.add("GRU", "REC", future, 500, 6)

    t = 1_000_000.0
    for i in range(6):
        mon.run_due(now=t + i * 6 * 3600)

    prices = [a["price"] for a in reversed(mon.list_alerts())]
    # 450 (entrou abaixo do alvo), 430 (novo mínimo), 440 (voltou abaixo após 800)
    assert prices == [450, 430, 440]


def test_monitor_respects_interval(db):
    fake = FakePrices([700, 700, 700])
    mon = MonitorService(db, fake)
    mon.add("GRU", "REC", date.today() + timedelta(days=10), 500, 6)
    mon.run_due(now=1_000_000)
    mon.run_due(now=1_000_000 + 3600)  # só 1 h depois: não checa
    assert fake.calls == 1


def test_monitor_deactivates_past_dates(db):
    mon = MonitorService(db, FakePrices([]))
    mid = mon.add("GRU", "REC", date.today() - timedelta(days=1), 500, 6)
    mon.run_due()
    assert db.scalar("SELECT active FROM monitors WHERE id = ?", (mid,)) == 0
