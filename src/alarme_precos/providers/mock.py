"""Provedor de demonstração, usado quando não há SERPAPI_API_KEY no .env.

Os preços são fictícios. A UI sempre exibe o aviso "DEMO" quando este
provedor está ativo.
"""

from __future__ import annotations

import random

from .base import BookingOption, FlightOffer, PriceProvider, SearchQuery, SearchResult

_AIRLINES = ["LATAM", "GOL", "Azul"]


class MockProvider(PriceProvider):
    name = "demo"
    is_demo = True

    def search(self, query: SearchQuery) -> SearchResult:
        # Mesma rota e data geram os mesmos valores, para a demo ser previsível.
        rng = random.Random(query.cache_key(self.name, "BRL"))
        base = rng.randint(250, 900)
        offers = []
        for i in range(5):
            hour = rng.randint(5, 22)
            minute = rng.choice([0, 15, 30, 45])
            duration = rng.randint(60, 300)
            end = hour * 60 + minute + duration
            offers.append(
                FlightOffer(
                    airline=_AIRLINES[i % len(_AIRLINES)],
                    price=float(base + rng.randint(-60, 180)),
                    departure_time=f"{query.outbound_date} {hour:02d}:{minute:02d}",
                    arrival_time=f"{query.outbound_date} {(end // 60) % 24:02d}:{end % 60:02d}",
                    duration_min=duration,
                    stops=rng.choice([0, 0, 1]),
                    flight_numbers=f"DEMO {1000 + i}",
                    is_best=i < 2,
                    booking_token=f"demo-{i}",
                )
            )
        offers.sort(key=lambda o: o.price)
        return SearchResult(provider=self.name, offers=offers, is_demo=True)

    def booking_options(self, query: SearchQuery, offer: FlightOffer) -> list[BookingOption]:
        # Nomes genéricos de propósito: a demo não atribui preços inventados a empresas reais.
        rng = random.Random(f"{offer.booking_token}:{offer.price}")
        sellers = [(f"Site da {offer.airline} (demo)", True, 0.0)]
        for name in ("Agência Demo A", "Agência Demo B"):
            if rng.random() < 0.7:
                sellers.append((name, False, rng.uniform(-0.06, 0.08)))
        options = [
            BookingOption(
                seller=name,
                is_airline=is_airline,
                price=round(offer.price * (1 + delta), 2),
                flight_numbers=offer.flight_numbers,
                fare_title="Econômica",
                baggage="1 bagagem de mão grátis",
            )
            for name, is_airline, delta in sellers
        ]
        return sorted(options, key=lambda o: o.price)
