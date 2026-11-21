"""Organização do resultado da busca: menor preço, companhia aérea e fonte de venda.

Funções puras (sem Gradio e sem rede), para facilitar os testes.
"""

from __future__ import annotations

import pandas as pd

from .fmt import br_datetime, brl
from .providers import BookingOption, FlightOffer

GROUP_PRICE = "💲 Menor preço"
GROUP_AIRLINE = "✈️ Companhia aérea"
GROUP_SOURCE = "🏷️ Fonte de venda"
GROUP_MODES = [GROUP_PRICE, GROUP_AIRLINE, GROUP_SOURCE]

OFFER_COLUMNS = ["#", "Companhia", "Preço", "Partida", "Chegada", "Duração", "Paradas", "Voo(s)", "Destaque"]
AIRLINE_SUMMARY_COLUMNS = ["Companhia", "Ofertas", "Menor preço", "Preço médio", "Mais rápido", "Voos diretos"]
SOURCE_SUMMARY_COLUMNS = ["Fonte", "Tipo", "Voos vendidos", "Menor preço", "Preço médio"]
SOURCE_COLUMNS = [
    "Fonte", "Tipo", "Companhia", "Voo(s)", "Partida", "Preço", "vs. site da cia", "Tarifa", "Bagagem", "Condições",
]


def fmt_duration(minutes: int | None) -> str:
    if not minutes:
        return "—"
    return f"{minutes // 60}h{minutes % 60:02d}"


def _offer_row(rank: int, o: FlightOffer) -> list:
    return [
        rank,
        o.airline,
        brl(o.price),
        br_datetime(o.departure_time),
        br_datetime(o.arrival_time),
        fmt_duration(o.duration_min),
        "Direto" if o.stops == 0 else str(o.stops),
        o.flight_numbers,
        "⭐ Melhor opção" if o.is_best else "",
    ]


def by_price(offers: list[FlightOffer]) -> pd.DataFrame:
    ordered = sorted(offers, key=lambda o: o.price)
    return pd.DataFrame([_offer_row(i, o) for i, o in enumerate(ordered, 1)], columns=OFFER_COLUMNS)


def by_airline(offers: list[FlightOffer]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Resumo por companhia (ordenado pelo menor preço de cada uma) e detalhe agrupado."""
    if not offers:
        return pd.DataFrame(columns=AIRLINE_SUMMARY_COLUMNS), pd.DataFrame(columns=OFFER_COLUMNS)

    raw = pd.DataFrame(
        {
            "airline": [o.airline for o in offers],
            "price": [o.price for o in offers],
            "duration": [o.duration_min for o in offers],
            "direct": [o.stops == 0 for o in offers],
        }
    )
    agg = (
        raw.groupby("airline")
        .agg(n_offers=("price", "size"), min_price=("price", "min"), mean_price=("price", "mean"),
             fastest=("duration", "min"), n_direct=("direct", "sum"))
        .sort_values(["min_price", "n_offers"], ascending=[True, False])
    )
    summary = pd.DataFrame(
        [
            [name, int(r.n_offers), brl(r.min_price), brl(r.mean_price),
             fmt_duration(None if pd.isna(r.fastest) else int(r.fastest)), int(r.n_direct)]
            for name, r in zip(agg.index, agg.itertuples(index=False))
        ],
        columns=AIRLINE_SUMMARY_COLUMNS,
    )
    order = {name: i for i, name in enumerate(agg.index)}
    ordered = sorted(offers, key=lambda o: (order[o.airline], o.price))
    detail = pd.DataFrame([_offer_row(i, o) for i, o in enumerate(ordered, 1)], columns=OFFER_COLUMNS)
    return summary, detail


def by_source(
    offers: list[FlightOffer], sources: dict[int, list[BookingOption]]
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Resumo por fonte de venda e detalhe (uma linha por fonte e voo).

    ``sources`` mapeia o índice da oferta em ``offers`` para as fontes consultadas.
    """
    rows = []
    for idx, options in sources.items():
        if idx >= len(offers):
            continue
        offer = offers[idx]
        airline_prices = [o.price for o in options if o.is_airline]
        ref = min(airline_prices) if airline_prices else None
        for opt in options:
            diff = None if ref is None or opt.is_airline else opt.price - ref
            rows.append(
                {
                    "seller": opt.seller,
                    "kind": "Companhia aérea" if opt.is_airline else "Agência",
                    "airline": offer.airline,
                    "flights": opt.flight_numbers or offer.flight_numbers,
                    "departure": br_datetime(offer.departure_time),
                    "price": opt.price,
                    "diff": diff,
                    "fare": opt.fare_title,
                    "baggage": opt.baggage,
                    "conditions": opt.conditions,
                }
            )
    if not rows:
        return pd.DataFrame(columns=SOURCE_SUMMARY_COLUMNS), pd.DataFrame(columns=SOURCE_COLUMNS)

    raw = pd.DataFrame(rows)
    agg = (
        raw.groupby(["seller", "kind"])
        .agg(n_offers=("price", "size"), min_price=("price", "min"), mean_price=("price", "mean"))
        .reset_index()
        .sort_values(["min_price", "n_offers"], ascending=[True, False])
    )
    summary = pd.DataFrame(
        [[r.seller, r.kind, int(r.n_offers), brl(r.min_price), brl(r.mean_price)] for r in agg.itertuples()],
        columns=SOURCE_SUMMARY_COLUMNS,
    )
    order = {s: i for i, s in enumerate(agg["seller"])}
    raw["_o"] = raw["seller"].map(order)
    raw = raw.sort_values(["_o", "price"])

    def fmt_diff(v):
        if v is None or pd.isna(v):
            return "—"
        if abs(v) < 0.005:
            return "mesmo preço"
        return ("−" if v < 0 else "+") + brl(abs(v))

    detail = pd.DataFrame(
        [
            [r.seller, r.kind, r.airline, r.flights, r.departure, brl(r.price), fmt_diff(r.diff),
             r.fare or "—", r.baggage or "—", r.conditions or "—"]
            for r in raw.itertuples()
        ],
        columns=SOURCE_COLUMNS,
    )
    return summary, detail


def pick_offers_for_sources(
    offers: list[FlightOffer], already: dict[int, list[BookingOption]], n: int
) -> list[int]:
    """Índices dos N voos mais baratos que ainda não tiveram as fontes consultadas."""
    ranked = sorted(range(len(offers)), key=lambda i: offers[i].price)
    eligible = [i for i in ranked if offers[i].booking_token]
    return [i for i in eligible[: max(0, n)] if i not in already]
