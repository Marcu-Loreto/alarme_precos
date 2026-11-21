"""Formatação compartilhada entre a UI e os alertas."""


def brl(value: float | None) -> str:
    """1234.5 -> 'R$ 1.234,50'."""
    if value is None:
        return "—"
    return "R$ " + f"{value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


DATE_FMT = "%d-%m-%Y"  # padrão brasileiro: DD-MM-AAAA


def br_date(value) -> str:
    """date, datetime ou '2026-12-20' -> '20-12-2026'."""
    from datetime import date as _date

    if value is None or value == "":
        return "—"
    if isinstance(value, str):
        try:
            value = _date.fromisoformat(value[:10])
        except ValueError:
            return value
    return value.strftime(DATE_FMT)


def br_datetime(value: str | None) -> str:
    """'2026-12-20 06:00' (formato do provedor) -> '20-12-2026 06:00'."""
    if not value:
        return "—"
    day, _, time_part = value.partition(" ")
    out = br_date(day)
    return f"{out} {time_part}".strip() if out != "—" else value
