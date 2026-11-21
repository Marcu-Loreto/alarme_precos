# ✈️ Alarme de Preços de Passagens

Busca preços **reais** de passagens aéreas no Google Flights, pela API do
[SerpApi](https://serpapi.com/google-flights-api), monitora rotas em background e
registra um alerta quando o preço fica abaixo do valor alvo. Um painel mostra
quanto da cota do SerpApi já foi usado.

Sem chave configurada, o app roda em **modo demonstração**, com preços fictícios
claramente marcados como DEMO.

## 🚀 Começando

```bash
# 1. Instale as dependências (requer uv: https://docs.astral.sh/uv/)
uv sync

# 2. Crie o .env a partir do modelo e coloque sua chave do SerpApi
cp .env.example .env
#    edite .env → SERPAPI_API_KEY=sua_chave

# 3. Rode
uv run alarme-precos
# → http://127.0.0.1:7860
```

Sem `uv`: `pip install -r requirements.txt && pip install -e . && alarme-precos`.

### Conseguindo a chave do SerpApi

1. Crie uma conta gratuita em <https://serpapi.com> (plano Free: 250 buscas/mês, 50 por hora).
2. Copie a chave em <https://serpapi.com/manage-api-key>.
3. Cole em `SERPAPI_API_KEY=` no arquivo `.env`.

## 🔑 Trocando de plano (sem mexer no código)

O `.env` é relido **a cada busca**. Quando o admin contratar um plano pago:

1. Troque `SERPAPI_API_KEY` no `.env` (ou mantenha a mesma chave, se o upgrade foi na mesma conta).
2. Pronto. Não é preciso reiniciar. A próxima busca já usa a nova chave, e o
   **Painel de Cota** passa a mostrar o novo plano e o novo limite.

Se o plano novo tiver limite por hora maior que 50, ajuste `SERPAPI_HOURLY_LIMIT` no `.env`.

## 🖥️ Telas

| Aba | O que faz |
|---|---|
| **🔍 Verificar Preços** | Data de ida e **data de volta opcional** (DD-MM-AAAA), 1 adulto, econômica. Com volta, cada trecho é buscado separadamente e aparece em sua própria tabela (valores da ida e valores da volta), além do total da ida + volta mais baratas. Mostra companhia, preço, horários, duração, paradas, a faixa de preço típica do Google e um link para abrir a mesma busca no Google Flights. O resultado pode ser organizado por **menor preço**, **companhia aérea** ou **fonte de venda** (veja abaixo). |
| **⏰ Monitoramento** | Cadastra rota, data, preço alvo e intervalo (padrão de 6 h). Uma thread em background checa as rotas e registra alertas quando o preço entra abaixo do alvo ou bate um novo mínimo. Monitores com data passada são desativados sozinhos. |
| **📊 Painel de Cota** | Plano atual (badge **PLANO FREE** ou **PLANO PAGO**), barra de uso, buscas restantes, uso na hora, data de renovação, registro local (buscas hoje e no mês, economia com cache) e **projeção de consumo** dos monitores ativos, com avisos quando a cota está perto do fim. |

## 🗂️ Organizar o resultado

| Opção | O que mostra | Custo |
|---|---|---|
| 💲 Menor preço | Todos os voos, do mais barato ao mais caro | grátis (reorganiza a busca já feita) |
| ✈️ Companhia aérea | Resumo por companhia (ofertas, menor preço, preço médio, voo mais rápido, diretos) + detalhe agrupado | grátis |
| 🏷️ Fonte de venda | Onde comprar cada voo: site da companhia ou agência, preço em cada uma, diferença para o site da companhia, tarifa e bagagem | **1 busca por voo consultado** |

A busca principal do Google Flights **não informa onde comprar**. As fontes vêm de
uma segunda consulta por voo (`booking_token`), e o SerpApi desconta cada uma da cota.
Por isso as fontes só são consultadas quando você clica em **🏷️ Buscar fontes de
venda**, e apenas para os **N voos mais baratos** (padrão 3, ajustável de 1 a 10). O
custo aparece antes do clique, e voos já consultados na última hora vêm do cache.

> As fontes são as que o **Google Flights** lista. Nos testes com voos nacionais
> (GRU→REC, GRU→SSA), apareceu só o site da companhia: nem toda agência repassa
> tarifas ao Google. Sites como 123milhas ou MaxMilhas só aparecem se o Google os
> listar para aquele voo.

## 🛫🛬 Ida e volta por trechos

Com a data de volta preenchida, o app faz **duas buscas de só ida**: origem→destino
na data de ida e destino→origem na data de volta. Cada trecho mostra seus próprios
voos e preços, e o resumo soma os dois mais baratos. A organização (menor preço,
companhia ou fonte) vale para os dois trechos.

- **Custo:** 2 buscas (1 por trecho). Fontes de venda: até N buscas **por trecho**.
- **Por que não usar a ida e volta do Google:** nesse modo o SerpApi devolve só o preço
  total do pacote, sem separar ida e volta, e também gasta 2 buscas.
- **Atenção:** em rotas internacionais, a tarifa de ida e volta comprada junta às
  vezes sai mais barata que a soma de dois trechos avulsos. Use o link "Abrir este
  trecho no Google Flights" para comparar.

## 💰 Como o app economiza cota

- **Cache local** (`ALARME_CACHE_TTL_MINUTES`, padrão de 60 min): repetir a mesma rota e data não gasta busca.
- **Só ida** (`type=2`): 1 busca por consulta. Ida e volta gastaria 2.
- **Trava por hora** (`SERPAPI_HOURLY_LIMIT`): bloqueia antes de o SerpApi recusar.
- **Trava de cota esgotada**: se o painel detectou saldo zero, as buscas reais ficam bloqueadas.
- O painel usa a **Account API** do SerpApi, que é gratuita e não consome buscas.

| Intervalo do monitor | Buscas/mês por rota | Rotas no plano Free |
|---|---|---|
| 6 h (padrão) | ~120 | 2 |
| 12 h | ~60 | 4 |
| 24 h | ~30 | 8 |

## ⚙️ Configuração (`.env`)

Veja todos os campos comentados em [`.env.example`](.env.example). Principais:

| Variável | Padrão | Uso |
|---|---|---|
| `SERPAPI_API_KEY` | vazio | Chave do SerpApi. Vazio = modo demo. |
| `SERPAPI_HOURLY_LIMIT` | 50 | Trava local por hora. |
| `ALARME_CACHE_TTL_MINUTES` | 60 | Validade do cache. |
| `ALARME_MONITOR_INTERVAL_HOURS` | 6 | Intervalo padrão dos monitores. |
| `GRADIO_SHARE` | false | Link público. Só sobe se `APP_AUTH_USER` e `APP_AUTH_PASSWORD` estiverem preenchidos. |

## 🏗️ Arquitetura

```
src/alarme_precos/
├── __init__.py        # main(): sobe a UI e a thread do monitor
├── app.py             # interface Gradio (3 abas)
├── config.py          # lê o .env a cada chamada
├── service.py         # PriceService (cache + travas) e QuotaService (painel)
├── monitor.py         # monitoramento em background e alertas
├── storage.py         # SQLite: cache, log de uso, monitores, alertas
├── grouping.py        # agrupamento: menor preço, companhia, fonte de venda
├── airports.py        # validação de IATA e de data, lista de aeroportos
├── fmt.py             # formatação em R$
└── providers/
    ├── base.py        # contrato PriceProvider
    ├── serpapi.py     # Google Flights via SerpApi
    └── mock.py        # modo demonstração
```

Para trocar de fornecedor (Duffel, Amadeus etc.), crie uma classe que implemente
`PriceProvider` e ajuste `service.build_provider`.

Os dados ficam em `data/alarme_precos.db`, ignorado pelo git.

## 🧪 Testes

```bash
uv run pytest      # 56 testes, sem rede (HTTP simulado)
uv run ruff check src tests
```

## ⚠️ Limitações

- Os alertas aparecem na aba Monitoramento. Notificação por e-mail ou Telegram ainda não foi implementada.
- A busca é para 1 adulto em classe econômica. Os monitores acompanham só a ida.
- O contador "Registro local" conta apenas buscas feitas por este app. O número oficial é o do bloco do SerpApi.
- O monitor roda dentro do processo da UI: se o app parar, as checagens param também.
- `alternative_approach.py` é um experimento antigo de scraping da Decolar e não é usado pelo app.
