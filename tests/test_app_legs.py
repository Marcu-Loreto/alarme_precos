from datetime import date

from alarme_precos.app import (
    OUT_TITLE,
    RET_TITLE,
    LegState,
    SearchState,
    render_all,
    result_summary,
)
from alarme_precos.grouping import GROUP_AIRLINE, GROUP_PRICE
from alarme_precos.providers import FlightOffer, SearchQuery, SearchResult


def result(*prices, airline="GOL"):
    offers = [FlightOffer(airline, p, "2026-12-20 08:00", "2026-12-20 10:00", 120, 0, "G3 1") for p in prices]
    return SearchResult("serpapi", offers)


OUT = SearchQuery("GRU", "REC", date(2026, 12, 20))
RET = SearchQuery("REC", "GRU", date(2026, 12, 27))


def test_summary_shows_each_leg_and_total():
    st = SearchState(LegState(OUT_TITLE, OUT, result(700, 650)), LegState(RET_TITLE, RET, result(500, airline="Azul")))
    text = result_summary(st)
    assert "Ida" in text and "Volta" in text
    assert "20-12-2026" in text and "27-12-2026" in text
    assert "R$ 650,00 + R$ 500,00 = R$ 1.150,00" in text
    assert "GOL na ida, Azul na volta" in text


def test_one_way_has_no_total_and_hides_return_box():
    st = SearchState(LegState(OUT_TITLE, OUT, result(700)))
    assert "Ida + volta" not in result_summary(st)
    outputs = render_all(st, GROUP_PRICE)
    assert len(outputs) == 7
    assert outputs[3]["visible"] is False


def test_return_leg_error_keeps_outbound():
    st = SearchState(LegState(OUT_TITLE, OUT, result(700)), LegState(RET_TITLE, RET, error="Limite por hora"))
    text = result_summary(st)
    assert "R$ 700,00" in text and "Limite por hora" in text and "Ida + volta" not in text
    _, out_det, _, box, _, ret_det, ret_note = render_all(st, GROUP_PRICE)
    assert len(out_det) == 1 and box["visible"] is True
    assert ret_det.empty and "Limite por hora" in ret_note


def test_grouping_applies_to_both_legs():
    st = SearchState(LegState(OUT_TITLE, OUT, result(700, 650)), LegState(RET_TITLE, RET, result(500, airline="Azul")))
    out_sum, _, out_note, _, ret_sum, _, ret_note = render_all(st, GROUP_AIRLINE)
    assert list(out_sum["value"]["Companhia"]) == ["GOL"]
    assert list(ret_sum["value"]["Companhia"]) == ["Azul"]
    assert out_note.startswith("### 🛫 Ida: GRU → REC") and ret_note.startswith("### 🛬 Volta: REC → GRU")
