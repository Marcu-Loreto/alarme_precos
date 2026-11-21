"""Monitoramento em background: checa cada rota no intervalo configurado."""

from __future__ import annotations

import logging
import threading
import time
from datetime import date

from .fmt import br_date, brl
from .providers import ProviderError, SearchQuery
from .service import PriceService
from .storage import Database

log = logging.getLogger(__name__)


class MonitorService:
    def __init__(self, db: Database, prices: PriceService, tick_seconds: float = 60):
        self.db = db
        self.prices = prices
        self.tick_seconds = tick_seconds
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    # ------------------------------------------------------------- cadastro
    def add(
        self, origin: str, destination: str, outbound_date: date, target_price: float, interval_hours: float
    ) -> int:
        return self.db.execute(
            "INSERT INTO monitors (origin, destination, outbound_date, target_price, interval_hours, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (origin, destination, outbound_date.isoformat(), target_price, interval_hours, time.time()),
        )

    def deactivate(self, monitor_id: int) -> bool:
        before = self.db.scalar("SELECT active FROM monitors WHERE id = ?", (monitor_id,))
        self.db.execute("UPDATE monitors SET active = 0 WHERE id = ?", (monitor_id,))
        return bool(before)

    def list_monitors(self, only_active: bool = False):
        sql = "SELECT * FROM monitors"
        if only_active:
            sql += " WHERE active = 1"
        return self.db.query(sql + " ORDER BY active DESC, id DESC")

    def list_alerts(self, limit: int = 50):
        return self.db.query(
            "SELECT a.*, m.origin, m.destination, m.outbound_date, m.target_price "
            "FROM alerts a JOIN monitors m ON m.id = a.monitor_id ORDER BY a.ts DESC LIMIT ?",
            (limit,),
        )

    # ------------------------------------------------------------ execução
    def run_due(self, now: float | None = None) -> int:
        """Checa os monitores vencidos. Devolve quantos foram consultados."""
        now = now or time.time()
        today = date.today().isoformat()
        self.db.execute("UPDATE monitors SET active = 0 WHERE active = 1 AND outbound_date < ?", (today,))

        checked = 0
        for row in self.list_monitors(only_active=True):
            last = row["last_checked"]
            if last is not None and now - last < row["interval_hours"] * 3600:
                continue
            self.check(row, now)
            checked += 1
        return checked

    def check(self, row, now: float | None = None) -> None:
        now = now or time.time()
        query = SearchQuery(row["origin"], row["destination"], date.fromisoformat(row["outbound_date"]))
        try:
            result = self.prices.search(query)
        except ProviderError as exc:
            log.warning("Monitor %s falhou: %s", row["id"], exc)
            self.db.execute(
                "UPDATE monitors SET last_checked = ?, last_error = ? WHERE id = ?", (now, str(exc), row["id"])
            )
            return

        cheapest = result.cheapest
        price = cheapest.price if cheapest else None
        previous = row["last_price"]
        target = row["target_price"]

        if price is not None and price <= target and (previous is None or previous > target or price < previous):
            prefix = "[DEMO] " if result.is_demo else ""
            self.db.execute(
                "INSERT INTO alerts (monitor_id, ts, price, airline, message) VALUES (?, ?, ?, ?, ?)",
                (
                    row["id"],
                    now,
                    price,
                    cheapest.airline,
                    (
                        f"{prefix}{row['origin']}→{row['destination']} em {br_date(row['outbound_date'])}: "
                        f"{brl(price)} ({cheapest.airline}), alvo {brl(target)}"
                    ),
                ),
            )
        self.db.execute(
            "UPDATE monitors SET last_checked = ?, last_price = ?, last_error = NULL WHERE id = ?",
            (now, price, row["id"]),
        )

    # ----------------------------------------------------------- thread
    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="price-monitor", daemon=True)
        self._thread.start()

    def shutdown(self) -> None:
        self._stop.set()

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                self.run_due()
            except Exception:  # a thread não pode morrer por um erro inesperado
                log.exception("Erro no ciclo do monitor")
            self._stop.wait(self.tick_seconds)
