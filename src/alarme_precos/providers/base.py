"""Contrato comum a todos os provedores de preço.

Para trocar de fornecedor (Duffel, Amadeus etc.), basta criar uma nova classe
que implemente ``PriceProvider`` e registrá-la em ``service.build_provider``.
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from datetime import date


class ProviderError(Exception):
    """Falha ao consultar o provedor (mensagem já pronta para o usuário)."""


class QuotaExceededError(ProviderError):
    """Cota mensal esgotada ou limite por hora atingido."""


@dataclass(frozen=True)
class SearchQuery:
    origin: str
    destination: str
    outbound_date: date
    adults: int = 1

    @property
    def route(self) -> str:
        return f"{self.origin}-{self.destination} {self.outbound_date.isoformat()}"

    def cache_key(self, provider: str, currency: str) -> str:
        return f"{provider}:{currency}:{self.origin}:{self.destination}:{self.outbound_date}:{self.adults}"


@dataclass
class FlightOffer:
    airline: str
    price: float
    departure_time: str
    arrival_time: str
    duration_min: int | None
    stops: int
    flight_numbers: str
    is_best: bool = False
    booking_token: str | None = None  # usado para consultar as fontes de venda


@dataclass
class BookingOption:
    """Onde comprar um voo: site da companhia ou agência (OTA)."""

    seller: str
    is_airline: bool
    price: float
    flight_numbers: str
    fare_title: str = ""
    baggage: str = ""
    conditions: str = ""


@dataclass
class SearchResult:
    provider: str
    offers: list[FlightOffer]
    is_demo: bool = False
    from_cache: bool = False
    price_insights: dict | None = None
    google_flights_url: str | None = None
    fetched_at: float = field(default_factory=time.time)

    @property
    def cheapest(self) -> FlightOffer | None:
        return min(self.offers, key=lambda o: o.price, default=None)

    def to_dict(self) -> dict:
        return {
            "provider": self.provider,
            "offers": [asdict(o) for o in self.offers],
            "is_demo": self.is_demo,
            "price_insights": self.price_insights,
            "google_flights_url": self.google_flights_url,
            "fetched_at": self.fetched_at,
        }

    @classmethod
    def from_dict(cls, data: dict, from_cache: bool = False) -> SearchResult:
        return cls(
            provider=data["provider"],
            offers=[FlightOffer(**o) for o in data["offers"]],
            is_demo=data.get("is_demo", False),
            from_cache=from_cache,
            price_insights=data.get("price_insights"),
            google_flights_url=data.get("google_flights_url"),
            fetched_at=data.get("fetched_at", time.time()),
        )


class PriceProvider(ABC):
    name: str = "base"
    is_demo: bool = False

    @abstractmethod
    def search(self, query: SearchQuery) -> SearchResult:
        """Consulta o provedor e devolve as ofertas encontradas."""

    def booking_options(self, query: SearchQuery, offer: FlightOffer) -> list[BookingOption]:
        """Fontes de venda de uma oferta. Provedores sem esse recurso devolvem []."""
        return []
