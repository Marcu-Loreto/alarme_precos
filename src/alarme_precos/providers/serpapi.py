"""Integração com a API Google Flights do SerpApi.

Docs: https://serpapi.com/google-flights-api e https://serpapi.com/account-api
"""

from __future__ import annotations

import logging

import requests

from .base import (
    BookingOption,
    FlightOffer,
    PriceProvider,
    ProviderError,
    QuotaExceededError,
    SearchQuery,
    SearchResult,
)

log = logging.getLogger(__name__)

SEARCH_URL = "https://serpapi.com/search"
ACCOUNT_URL = "https://serpapi.com/account"
TIMEOUT = (5, 30)  # conexão, leitura (segundos)
NO_RESULTS_HINT = "hasn't returned any results"


class SerpApiProvider(PriceProvider):
    name = "serpapi"
    is_demo = False

    def __init__(
        self,
        api_key: str,
        currency: str = "BRL",
        language: str = "pt",
        country: str = "br",
        session: requests.Session | None = None,
    ):
        if not api_key:
            raise ValueError("api_key é obrigatória")
        self._api_key = api_key
        self.currency = currency
        self.language = language
        self.country = country
        self._session = session or requests.Session()

    # ------------------------------------------------------------------ busca
    def _base_params(self, query: SearchQuery) -> dict:
        return {
            "engine": "google_flights",
            "departure_id": query.origin,
            "arrival_id": query.destination,
            "outbound_date": query.outbound_date.isoformat(),
            "type": 2,  # só ida: 1 busca por consulta (ida e volta gastaria 2)
            "adults": query.adults,
            "currency": self.currency,
            "hl": self.language,
            "gl": self.country,
            "api_key": self._api_key,
        }

    def search(self, query: SearchQuery) -> SearchResult:
        data = self._get(SEARCH_URL, self._base_params(query))
        _raise_for_error(data)

        offers = [
            *(o for o in (_parse_offer(i, True) for i in data.get("best_flights", [])) if o),
            *(o for o in (_parse_offer(i, False) for i in data.get("other_flights", [])) if o),
        ]
        offers.sort(key=lambda o: o.price)
        return SearchResult(
            provider=self.name,
            offers=offers,
            price_insights=data.get("price_insights"),
            google_flights_url=(data.get("search_metadata") or {}).get("google_flights_url"),
        )

    # ----------------------------------------------------------------- fontes
    def booking_options(self, query: SearchQuery, offer: FlightOffer) -> list[BookingOption]:
        """Onde comprar o voo. Cada chamada consome 1 busca da cota."""
        if not offer.booking_token:
            return []
        data = self._get(SEARCH_URL, {**self._base_params(query), "booking_token": offer.booking_token})
        _raise_for_error(data)
        options = [o for o in (_parse_booking(i) for i in data.get("booking_options", [])) if o]
        options.sort(key=lambda o: o.price)
        return options

    # ------------------------------------------------------------------ conta
    def fetch_account(self) -> dict:
        """Dados do plano e da cota. A Account API é gratuita e não consome cota."""
        return self._get(ACCOUNT_URL, {"api_key": self._api_key})

    # ---------------------------------------------------------------- interno
    def _get(self, url: str, params: dict) -> dict:
        try:
            resp = self._session.get(url, params=params, timeout=TIMEOUT)
        except requests.Timeout as exc:
            raise ProviderError("SerpApi não respondeu a tempo. Tente novamente.") from exc
        except requests.RequestException as exc:
            log.warning("Falha de rede ao chamar SerpApi: %s", exc.__class__.__name__)
            raise ProviderError("Não foi possível conectar ao SerpApi.") from exc

        if resp.status_code == 401:
            raise ProviderError("Chave do SerpApi inválida. Confira SERPAPI_API_KEY no .env.")
        if resp.status_code == 429:
            raise QuotaExceededError(
                "SerpApi recusou a busca: cota do plano esgotada ou limite por hora atingido."
            )
        if resp.status_code == 403:
            raise ProviderError("Conta SerpApi sem permissão (conta inativa ou excluída).")

        try:
            data = resp.json()
        except ValueError as exc:
            raise ProviderError(f"Resposta inválida do SerpApi (HTTP {resp.status_code}).") from exc

        if resp.status_code >= 400:
            raise ProviderError(f"SerpApi: {data.get('error', f'HTTP {resp.status_code}')}")
        return data


def _raise_for_error(data: dict) -> None:
    error = data.get("error")
    if error and NO_RESULTS_HINT not in error:
        log.warning("SerpApi retornou erro: %s", error)
        raise ProviderError(f"SerpApi: {error}")


def _parse_booking(item: dict) -> BookingOption | None:
    # Bilhete único vem em "together". Bilhetes separados (raro em só ida) vêm em "departing".
    part = item.get("together") or {}
    if item.get("separate_tickets") and item.get("departing"):
        part = item["departing"]
    price = part.get("price")
    seller = part.get("book_with")
    if price is None or not seller:
        return None
    return BookingOption(
        seller=seller,
        is_airline=bool(part.get("airline")),
        price=float(price),
        flight_numbers=", ".join(part.get("marketed_as") or []),
        fare_title=part.get("option_title") or "",
        baggage="; ".join(part.get("baggage_prices") or []),
        conditions="; ".join(part.get("extensions") or []),
    )


def _parse_offer(item: dict, is_best: bool) -> FlightOffer | None:
    price = item.get("price")
    legs = item.get("flights") or []
    if price is None or not legs:
        return None

    airlines = list(dict.fromkeys(leg.get("airline", "?") for leg in legs))
    return FlightOffer(
        airline=" + ".join(airlines),
        price=float(price),
        departure_time=legs[0].get("departure_airport", {}).get("time", ""),
        arrival_time=legs[-1].get("arrival_airport", {}).get("time", ""),
        duration_min=item.get("total_duration"),
        stops=len(item.get("layovers") or []),
        flight_numbers=", ".join(leg.get("flight_number", "") for leg in legs if leg.get("flight_number")),
        is_best=is_best,
        booking_token=item.get("booking_token"),
    )
