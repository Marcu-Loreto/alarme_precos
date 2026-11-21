"""Aeroportos sugeridos na UI e validação de códigos IATA."""

from __future__ import annotations

import re
from datetime import date, datetime

AIRPORTS: dict[str, str] = {
    "GRU": "São Paulo (Guarulhos)",
    "CGH": "São Paulo (Congonhas)",
    "VCP": "Campinas (Viracopos)",
    "GIG": "Rio de Janeiro (Galeão)",
    "SDU": "Rio de Janeiro (Santos Dumont)",
    "BSB": "Brasília",
    "CNF": "Belo Horizonte (Confins)",
    "SSA": "Salvador",
    "REC": "Recife",
    "FOR": "Fortaleza",
    "NAT": "Natal",
    "MCZ": "Maceió",
    "AJU": "Aracaju",
    "JPA": "João Pessoa",
    "SLZ": "São Luís",
    "THE": "Teresina",
    "BEL": "Belém",
    "MAO": "Manaus",
    "CWB": "Curitiba",
    "FLN": "Florianópolis",
    "POA": "Porto Alegre",
    "NVT": "Navegantes",
    "IGU": "Foz do Iguaçu",
    "VIX": "Vitória",
    "GYN": "Goiânia",
    "CGB": "Cuiabá",
    "CGR": "Campo Grande",
    "PMW": "Palmas",
    "PVH": "Porto Velho",
    "RBR": "Rio Branco",
    "BPS": "Porto Seguro",
    "EZE": "Buenos Aires (Ezeiza)",
    "SCL": "Santiago",
    "LIM": "Lima",
    "BOG": "Bogotá",
    "MIA": "Miami",
    "MCO": "Orlando",
    "JFK": "Nova York (JFK)",
    "LIS": "Lisboa",
    "MAD": "Madri",
    "CDG": "Paris (Charles de Gaulle)",
    "LHR": "Londres (Heathrow)",
}

AIRPORT_CHOICES = [f"{code} — {name}" for code, name in AIRPORTS.items()]

_IATA_RE = re.compile(r"^[A-Z]{3}$")


def parse_iata(value: str | None, field: str = "Aeroporto") -> str:
    """Aceita 'GRU', 'gru' ou 'GRU — São Paulo (Guarulhos)'. Devolve 'GRU'."""
    code = (value or "").strip().split(" ")[0].strip().upper()
    if not _IATA_RE.match(code):
        raise ValueError(f"{field}: informe um código IATA de 3 letras (ex.: GRU).")
    return code


def parse_future_date(value: str | None, today: date | None = None) -> date:
    """Valida data no padrão brasileiro DD-MM-AAAA (aceita também DD/MM/AAAA), de hoje em diante."""
    raw = (value or "").strip()
    for fmt in ("%d-%m-%Y", "%d/%m/%Y", "%Y-%m-%d"):
        try:
            parsed = datetime.strptime(raw, fmt).date()
            break
        except ValueError:
            continue
    else:
        raise ValueError("Data: use o formato DD-MM-AAAA (ex.: 20-12-2026).")
    if parsed < (today or date.today()):
        raise ValueError("Data: escolha uma data de hoje em diante.")
    return parsed


def label(code: str) -> str:
    name = AIRPORTS.get(code)
    return f"{code} ({name})" if name else code
