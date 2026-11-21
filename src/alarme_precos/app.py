"""Interface Gradio: busca de preços, monitoramento e painel de cota."""

from __future__ import annotations

import html
import logging
from dataclasses import dataclass, field
from datetime import datetime

import gradio as gr
import pandas as pd

from .airports import AIRPORT_CHOICES, label, parse_future_date, parse_iata
from .config import get_settings
from .fmt import br_date, brl
from .grouping import (
    GROUP_AIRLINE,
    GROUP_MODES,
    GROUP_PRICE,
    GROUP_SOURCE,
    OFFER_COLUMNS,
    by_airline,
    by_price,
    by_source,
    pick_offers_for_sources,
)
from .monitor import MonitorService
from .providers import BookingOption, ProviderError, SearchQuery, SearchResult
from .service import PriceService, QuotaService, QuotaStatus
from .storage import Database

log = logging.getLogger(__name__)

MONITOR_COLUMNS = ["ID", "Rota", "Data", "Alvo", "Último preço", "Intervalo", "Última checagem", "Status"]
ALERT_COLUMNS = ["Quando", "Rota", "Data", "Preço", "Companhia", "Alvo"]


# ------------------------------------------------------------- formatação
def fmt_ts(ts: float | None) -> str:
    return datetime.fromtimestamp(ts).strftime("%d-%m %H:%M") if ts else "—"


OUT_TITLE = "🛫 Ida"
RET_TITLE = "🛬 Volta"


@dataclass
class LegState:
    """Um trecho da viagem (ida ou volta) e seu resultado."""

    title: str
    query: SearchQuery
    result: SearchResult | None = None
    error: str | None = None
    sources: dict[int, list[BookingOption]] = field(default_factory=dict)

    @property
    def heading(self) -> str:
        q = self.query
        return f"### {self.title}: {q.origin} → {q.destination} · {br_date(q.outbound_date)}"


@dataclass
class SearchState:
    """Última busca da sessão: permite reorganizar o resultado sem gastar cota."""

    outbound: LegState
    inbound: LegState | None = None

    @property
    def legs(self) -> list[LegState]:
        return [leg for leg in (self.outbound, self.inbound) if leg is not None]


def render_leg(leg: LegState | None, mode: str):
    """Devolve (resumo por grupo, tabela de detalhe, nota) de um trecho."""
    hidden = gr.update(value=None, visible=False)
    empty = pd.DataFrame(columns=OFFER_COLUMNS)
    if leg is None:
        return hidden, empty, ""
    if leg.result is None:
        return hidden, empty, f"{leg.heading}\n❌ {leg.error or 'Busca não realizada.'}"
    offers = leg.result.offers
    head = leg.heading + "\n"

    if mode == GROUP_AIRLINE:
        summary, detail = by_airline(offers)
        note = f"{len(summary)} companhia(s) encontrada(s). Reorganizar o resultado não gasta cota."
        return (gr.update(value=summary, visible=True, label=f"Resumo por companhia aérea: {leg.title}"),
                detail, head + note)

    if mode == GROUP_SOURCE:
        if not leg.sources:
            note = (
                "🏷️ A busca principal não informa **onde comprar**. Para ver as fontes de venda "
                "(site da companhia ou agências), use **Buscar fontes de venda** ao lado. "
                + ("Na demo não há custo." if leg.result.is_demo else "Cada voo consultado gasta 1 busca da cota.")
            )
            return hidden, empty, head + note
        summary, detail = by_source(offers, leg.sources)
        sellers = len(summary)
        note = f"Fontes consultadas para {len(leg.sources)} de {len(offers)} voo(s): {sellers} fonte(s) encontrada(s)."
        if sellers > 0 and (summary["Tipo"] == "Companhia aérea").all():
            note += (
                " O Google Flights listou só o site das companhias para esses voos. É comum em voos "
                "nacionais: nem toda agência repassa tarifas ao Google."
            )
        return (gr.update(value=summary, visible=True, label=f"Resumo por fonte de venda: {leg.title}"),
                detail, head + note)

    return hidden, by_price(offers), head + f"{len(offers)} voo(s), do mais barato para o mais caro."


def render_all(state: SearchState | None, mode: str):
    """Saídas da ida (3), visibilidade do bloco da volta (1) e saídas da volta (3)."""
    out = render_leg(state.outbound if state else None, mode)
    inbound = state.inbound if state else None
    ret = render_leg(inbound, mode)
    return (*out, gr.update(visible=inbound is not None), *ret)


def mode_banner() -> str:
    s = get_settings()
    if s.has_api_key:
        return "🟢 **Preços reais** via SerpApi (Google Flights). A chave é lida do `.env`."
    return (
        "🟡 **MODO DEMONSTRAÇÃO**: os preços abaixo são fictícios. "
        "Para buscar preços reais, defina `SERPAPI_API_KEY` no arquivo `.env`."
    )


def _leg_summary(leg: LegState) -> list[str]:
    q = leg.query
    parts = [f"**{leg.title}: {label(q.origin)} → {label(q.destination)}** em {br_date(q.outbound_date)}"]
    result = leg.result
    if result is None:
        parts.append(f"❌ {leg.error}")
        return parts
    if result.is_demo:
        parts.append("⚠️ **DEMO: preços fictícios.**")
    elif result.from_cache:
        parts.append(f"♻️ Resultado do cache de {fmt_ts(result.fetched_at)} (não consumiu cota).")
    else:
        parts.append("✅ Busca real no SerpApi (1 busca consumida da cota).")
    if not result.offers:
        parts.append("Nenhum voo encontrado para esse trecho e data.")
    elif result.cheapest:
        parts.append(f"Menor preço: **{brl(result.cheapest.price)}** ({result.cheapest.airline}).")
    insights = result.price_insights or {}
    if insights.get("typical_price_range"):
        faixa = " a ".join(brl(v) for v in insights["typical_price_range"])
        nivel = {"low": "baixo", "typical": "normal", "high": "alto"}.get(insights.get("price_level"), "")
        parts.append(f"Faixa típica no Google: {faixa}" + (f" (preço atual: **{nivel}**)." if nivel else "."))
    if result.google_flights_url:
        parts.append(f"[🔗 Abrir este trecho no Google Flights]({result.google_flights_url})")
    return parts


def result_summary(state: SearchState) -> str:
    blocks = ["  \n".join(_leg_summary(leg)) for leg in state.legs]
    out, ret = state.outbound, state.inbound
    if ret and out.result and ret.result and out.result.cheapest and ret.result.cheapest:
        a, b = out.result.cheapest, ret.result.cheapest
        blocks.append(
            f"💰 **Ida + volta mais baratas: {brl(a.price)} + {brl(b.price)} = {brl(a.price + b.price)}**  \n"
            f"<small>Soma dos trechos avulsos mais baratos ({a.airline} na ida, {b.airline} na volta). "
            "Cada trecho é comprado separadamente.</small>"
        )
    return "\n\n".join(blocks)


def quota_html(st: QuotaStatus) -> str:
    e = html.escape

    def card(title: str, value: str, hint: str = "") -> str:
        return (
            '<div style="border:1px solid var(--border-color-primary);border-radius:10px;padding:14px 16px;">'
            f'<div style="font-size:.8rem;opacity:.7;text-transform:uppercase;letter-spacing:.05em">{e(title)}</div>'
            f'<div style="font-size:1.6rem;font-weight:700;margin-top:2px">{e(value)}</div>'
            f'<div style="font-size:.85rem;opacity:.7">{e(hint)}</div></div>'
        )

    grid = 'style="display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px;margin:12px 0"'
    local = (
        f"<div {grid}>"
        + card("Buscas reais hoje", str(st.local_calls_today), "registradas por este app")
        + card("Buscas reais no mês", str(st.local_calls_month), "desde o dia 1, por este app")
        + card("Economia com cache", str(st.cache_hits_month), "consultas no mês sem gastar cota")
        + card("Projeção dos monitores", f"{st.monitors_projection}/mês", "consumo estimado dos monitores ativos")
        + "</div>"
    )

    if st.mode == "demo":
        return (
            '<div style="padding:14px 16px;border-radius:10px;background:rgba(234,179,8,.15)">'
            "<b>Modo demonstração.</b> Nenhuma chave SerpApi configurada, então nenhuma cota é consumida. "
            "Para ativar preços reais, crie uma conta em serpapi.com, copie a chave e defina "
            "<code>SERPAPI_API_KEY</code> no arquivo <code>.env</code>. Não é preciso reiniciar o app.</div>"
            + local
        )

    if st.error:
        return (
            '<div style="padding:14px 16px;border-radius:10px;background:rgba(239,68,68,.15)">'
            f"<b>Não foi possível ler a conta SerpApi:</b> {e(st.error)}</div>" + local
        )

    pct = st.usage_percent or 0.0
    color = "#16a34a" if pct < 70 else "#d97706" if pct < 90 else "#dc2626"
    plan_badge = (
        '<span style="background:#2563eb;color:#fff;border-radius:999px;padding:2px 10px;font-size:.8rem">PLANO FREE</span>'
        if st.is_free_plan
        else '<span style="background:#16a34a;color:#fff;border-radius:999px;padding:2px 10px;font-size:.8rem">PLANO PAGO</span>'
    )
    warn = ""
    if st.total_searches_left is not None and st.total_searches_left <= 0:
        warn = "🚫 Cota esgotada. As buscas reais estão bloqueadas até a renovação ou a troca de plano."
    elif pct >= 90:
        warn = "⚠️ Mais de 90% da cota usada. Considere aumentar o intervalo dos monitores ou contratar um plano maior."
    elif st.plan_searches_left is not None and st.monitors_projection > (st.searches_per_month or 0):
        warn = "⚠️ A projeção dos monitores passa da cota mensal do plano. Aumente o intervalo ou reduza as rotas."
    warn_html = (
        f'<div style="margin-top:10px;padding:10px 14px;border-radius:8px;background:rgba(217,119,6,.15)">{e(warn)}</div>'
        if warn
        else ""
    )

    used = st.this_month_usage or 0
    total = st.searches_per_month or 0
    remote = (
        f"<div {grid}>"
        + card("Usadas no ciclo", f"{used} / {total}", "dados oficiais do SerpApi")
        + card("Restantes", str(st.total_searches_left if st.total_searches_left is not None else "—"),
               f"plano {st.plan_searches_left} + créditos extras {st.extra_credits or 0}")
        + card("Nesta hora", f"{st.this_hour_searches or 0} / {st.rate_limit_per_hour or '—'}", "limite por hora do plano")
        + card("Renovação", st.renewal_date or "—", "reinício da cota")
        + "</div>"
    )
    return (
        f'<div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap">'
        f'<span style="font-size:1.2rem;font-weight:700">{e(st.plan_name or "Plano SerpApi")}</span>{plan_badge}'
        f'<span style="opacity:.6;font-size:.85rem">atualizado {fmt_ts(st.fetched_at)}</span></div>'
        f'<div style="margin-top:12px;height:14px;border-radius:999px;background:rgba(127,127,127,.2);overflow:hidden">'
        f'<div style="height:100%;width:{pct:.1f}%;background:{color}"></div></div>'
        f'<div style="font-size:.85rem;opacity:.75;margin-top:4px">{pct:.1f}% da cota mensal usada</div>'
        + warn_html
        + remote
        + "<h4 style='margin:18px 0 0'>Registro local deste app</h4>"
        + local
    )


# -------------------------------------------------------------------- UI
def create_interface(db: Database | None = None) -> tuple[gr.Blocks, MonitorService]:
    settings = get_settings()
    db = db or Database(settings.db_path)
    quota = QuotaService(db)
    prices = PriceService(db, quota)
    monitor = MonitorService(db, prices)

    # ---- callbacks
    def _search_leg(leg: LegState) -> None:
        try:
            leg.result = prices.search(leg.query)
        except ProviderError as exc:
            leg.error = str(exc)
        except Exception:
            log.exception("Erro inesperado na busca")
            leg.error = "Erro inesperado na busca. Veja os logs do servidor."

    def do_search(origin, destination, date_text, return_text, mode):
        def fail(msg):
            return (msg, None, *render_all(None, mode))

        try:
            o, d = parse_iata(origin, "Origem"), parse_iata(destination, "Destino")
            if o == d:
                raise ValueError("Origem e destino precisam ser diferentes.")
            out_date = parse_future_date(date_text)
            ret_date = None
            if (return_text or "").strip():
                ret_date = parse_future_date(return_text)
                if ret_date < out_date:
                    raise ValueError("A data de volta precisa ser igual ou posterior à data de ida.")
        except ValueError as exc:
            return fail(f"❌ {exc}")

        state = SearchState(LegState(OUT_TITLE, SearchQuery(o, d, out_date)))
        _search_leg(state.outbound)
        if state.outbound.result is None:
            return fail(f"❌ {state.outbound.error}")
        if ret_date is not None:
            state.inbound = LegState(RET_TITLE, SearchQuery(d, o, ret_date))
            _search_leg(state.inbound)
        return (result_summary(state), state, *render_all(state, mode))

    def do_fetch_sources(state: SearchState | None, n):
        if state is None:
            return (gr.update(), state, *render_all(None, GROUP_SOURCE))
        n = int(n or 3)
        error = None
        consulted = 0
        for leg in state.legs:
            if leg.result is None or error:
                continue
            for idx in pick_offers_for_sources(leg.result.offers, leg.sources, n):
                try:
                    leg.sources[idx] = prices.booking_options(leg.query, leg.result.offers[idx])
                    consulted += 1
                except ProviderError as exc:
                    error = str(exc)
                    break  # cota/limite: não insiste nos próximos
                except Exception:
                    log.exception("Erro inesperado ao consultar fontes")
                    error = "Erro inesperado ao consultar fontes."
                    break
        outputs = list(render_all(state, GROUP_SOURCE))
        if error:
            outputs[2] = f"❌ {error}\n\n{outputs[2]}"
        elif consulted == 0:
            outputs[2] = "Esses voos já tiveram as fontes consultadas (nenhuma busca gasta).\n\n" + outputs[2]
        return (gr.update(value=GROUP_SOURCE), state, *outputs)

    def sources_cost_hint(n, return_text=""):
        n = int(n or 3)
        legs = 2 if (return_text or "").strip() else 1
        if not get_settings().has_api_key:
            return "<small>Demo: consultar fontes não gasta cota.</small>"
        left = quota.known_remaining()
        tail = f" Restam {left} buscas no plano." if left is not None else ""
        trecho = "em cada trecho (ida e volta)" if legs == 2 else ""
        return (
            f"<small>Consultar as fontes dos {n} voos mais baratos {trecho} gasta **até {n * legs} buscas** "
            f"(voos já consultados na última hora saem do cache, sem custo).{tail}</small>"
        )

    def monitors_frame():
        rows = []
        for r in monitor.list_monitors():
            status = "Ativo" if r["active"] else "Parado"
            if r["active"] and r["last_error"]:
                status = f"Erro: {r['last_error'][:60]}"
            rows.append([
                r["id"], f"{r['origin']}→{r['destination']}", br_date(r["outbound_date"]), brl(r["target_price"]),
                brl(r["last_price"]), f"{r['interval_hours']:g} h", fmt_ts(r["last_checked"]), status,
            ])
        return pd.DataFrame(rows, columns=MONITOR_COLUMNS)

    def alerts_frame():
        rows = [
            [fmt_ts(a["ts"]), f"{a['origin']}→{a['destination']}", br_date(a["outbound_date"]), brl(a["price"]),
             a["airline"] or "", brl(a["target_price"])]
            for a in monitor.list_alerts()
        ]
        return pd.DataFrame(rows, columns=ALERT_COLUMNS)

    def refresh_monitor_tables():
        return monitors_frame(), alerts_frame()

    def do_add_monitor(origin, destination, date_text, target, interval):
        try:
            o, d = parse_iata(origin, "Origem"), parse_iata(destination, "Destino")
            when = parse_future_date(date_text)
            if o == d:
                raise ValueError("Origem e destino precisam ser diferentes.")
            if target is None or float(target) <= 0:
                raise ValueError("Preço alvo: informe um valor maior que zero.")
        except ValueError as exc:
            return f"❌ {exc}", *refresh_monitor_tables()
        interval = max(1.0, float(interval or settings.monitor_interval_hours))
        mid = monitor.add(o, d, when, float(target), interval)
        monitor.run_due()  # primeira checagem imediata
        per_month = int(30 * 24 / interval)
        msg = (
            f"✅ Monitor #{mid} criado: {o}→{d} em {br_date(when)}, alvo {brl(float(target))}, "
            f"a cada {interval:g} h (~{per_month} buscas/mês)."
        )
        return msg, *refresh_monitor_tables()

    def do_stop_monitor(monitor_id):
        if not monitor_id:
            return "❌ Informe o ID do monitor.", *refresh_monitor_tables()
        ok = monitor.deactivate(int(monitor_id))
        msg = f"⏹️ Monitor #{int(monitor_id)} parado." if ok else f"Monitor #{int(monitor_id)} já estava parado ou não existe."
        return msg, *refresh_monitor_tables()

    def refresh_quota(force: bool = False):
        return quota_html(quota.status(force=force)), mode_banner()

    # ---- layout
    with gr.Blocks(title="Alarme de Preços de Passagens") as demo:
        gr.Markdown("# ✈️ Alarme de Preços de Passagens")
        banner = gr.Markdown(mode_banner())

        with gr.Tab("🔍 Verificar Preços"):
            with gr.Row():
                with gr.Column(scale=1):
                    origin = gr.Dropdown(AIRPORT_CHOICES, label="Origem (IATA)", allow_custom_value=True,
                                         value="GRU — São Paulo (Guarulhos)")
                    destination = gr.Dropdown(AIRPORT_CHOICES, label="Destino (IATA)", allow_custom_value=True,
                                              value="REC — Recife")
                    date_in = gr.Textbox(label="Data de ida", placeholder="DD-MM-AAAA, ex.: 20-12-2026")
                    return_in = gr.Textbox(label="Data de volta (opcional)",
                                           placeholder="DD-MM-AAAA, deixe vazio para só ida")
                    search_btn = gr.Button("🔍 Buscar preços", variant="primary")
                    gr.Markdown(
                        f"<small>1 adulto, classe econômica. Só ida gasta 1 busca; com volta são 2 "
                        f"(um valor para cada trecho). Repetir a mesma busca em até "
                        f"{settings.cache_ttl_minutes} min usa o cache e não gasta cota.</small>"
                    )
                    gr.Markdown("---")
                    n_sources = gr.Slider(1, 10, value=3, step=1, label="Fontes de venda: consultar os N voos mais baratos")
                    sources_hint = gr.Markdown(sources_cost_hint(3))
                    sources_btn = gr.Button("🏷️ Buscar fontes de venda")
                with gr.Column(scale=2):
                    summary = gr.Markdown()
                    group_mode = gr.Radio(GROUP_MODES, value=GROUP_PRICE, label="Organizar resultado por")
                    out_note = gr.Markdown()
                    out_summary = gr.Dataframe(label="Resumo por grupo", interactive=False, wrap=True, visible=False)
                    out_detail = gr.Dataframe(headers=OFFER_COLUMNS, label="Voos da ida", interactive=False, wrap=True)
                    with gr.Group(visible=False) as ret_box:
                        ret_note = gr.Markdown()
                        ret_summary = gr.Dataframe(label="Resumo por grupo", interactive=False, wrap=True,
                                                   visible=False)
                        ret_detail = gr.Dataframe(headers=OFFER_COLUMNS, label="Voos da volta", interactive=False,
                                                  wrap=True)
            search_state = gr.State(None)
            leg_outputs = [out_summary, out_detail, out_note, ret_box, ret_summary, ret_detail, ret_note]
            search_btn.click(
                do_search, [origin, destination, date_in, return_in, group_mode],
                [summary, search_state, *leg_outputs],
            ).then(sources_cost_hint, [n_sources, return_in], [sources_hint])
            group_mode.input(render_all, [search_state, group_mode], leg_outputs)
            sources_btn.click(
                do_fetch_sources, [search_state, n_sources], [group_mode, search_state, *leg_outputs],
            ).then(sources_cost_hint, [n_sources, return_in], [sources_hint])
            n_sources.change(sources_cost_hint, [n_sources, return_in], [sources_hint])
            return_in.change(sources_cost_hint, [n_sources, return_in], [sources_hint])

        with gr.Tab("⏰ Monitoramento"):
            with gr.Row():
                with gr.Column(scale=1):
                    m_origin = gr.Dropdown(AIRPORT_CHOICES, label="Origem (IATA)", allow_custom_value=True)
                    m_dest = gr.Dropdown(AIRPORT_CHOICES, label="Destino (IATA)", allow_custom_value=True)
                    m_date = gr.Textbox(label="Data de ida", placeholder="DD-MM-AAAA, ex.: 20-12-2026")
                    m_target = gr.Number(label="Preço alvo (R$)", minimum=1)
                    m_interval = gr.Slider(1, 24, value=settings.monitor_interval_hours, step=1,
                                           label="Intervalo de checagem (horas)")
                    gr.Markdown(
                        "<small>No plano Free (250 buscas/mês), checar a cada 6 h usa cerca de 120 buscas por "
                        "rota, então cabem 2 rotas. O consumo aparece no Painel de Cota.</small>"
                    )
                    add_btn = gr.Button("🚀 Criar monitor", variant="primary")
                    m_msg = gr.Markdown()
                    with gr.Row():
                        stop_id = gr.Number(label="ID do monitor", precision=0)
                        stop_btn = gr.Button("⏹️ Parar monitor")
                with gr.Column(scale=2):
                    monitors_df = gr.Dataframe(headers=MONITOR_COLUMNS, label="Monitores", interactive=False, wrap=True)
                    alerts_df = gr.Dataframe(headers=ALERT_COLUMNS, label="🎉 Alertas (preço abaixo do alvo)",
                                             interactive=False, wrap=True)
                    refresh_m_btn = gr.Button("🔄 Atualizar")
            add_btn.click(do_add_monitor, [m_origin, m_dest, m_date, m_target, m_interval], [m_msg, monitors_df, alerts_df])
            stop_btn.click(do_stop_monitor, [stop_id], [m_msg, monitors_df, alerts_df])
            refresh_m_btn.click(refresh_monitor_tables, None, [monitors_df, alerts_df])

        with gr.Tab("📊 Painel de Cota"):
            gr.Markdown(
                "Consumo da cota do SerpApi. Os números oficiais vêm da Account API do SerpApi, "
                "que é gratuita e não gasta buscas. Ao contratar um plano maior, basta trocar a "
                "`SERPAPI_API_KEY` no `.env`: o painel passa a mostrar o novo plano."
            )
            quota_panel = gr.HTML()
            refresh_q_btn = gr.Button("🔄 Atualizar agora")
            refresh_q_btn.click(lambda: refresh_quota(force=True), None, [quota_panel, banner])

        timer = gr.Timer(60)
        timer.tick(refresh_monitor_tables, None, [monitors_df, alerts_df])
        timer.tick(refresh_quota, None, [quota_panel, banner])
        demo.load(refresh_monitor_tables, None, [monitors_df, alerts_df])
        demo.load(refresh_quota, None, [quota_panel, banner])

    return demo, monitor
