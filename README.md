# Stock Screener (Domain-Driven Design reference implementation)

A small, dependency-free Python reference implementation of a stock-screening system built with
Domain-Driven Design: bounded contexts, value objects, aggregate roots, an anti-corruption layer
and an in-process event bus. Given market data (OHLC plus metrics such as PE and ROE) it evaluates
a `Screen` made of `Criterion` rules and returns matched stocks, per-stock scores and domain events.
It ships with in-memory repositories only; there is no live data feed.

> Status: research and education only; not investment advice. Phases 1-2 (Market Data, Stock
> Analysis) are implemented; Phases 3-6 are empty package skeletons.

## What it does
- Models market data (`Ticker`, `Price`, `OHLC`, `MarketData`, `MarketCalendar`) with self-validating value objects.
- Models screening (`Criterion`, `Screen`, `Stock` aggregate, `StockScore`); operators `<  >  ==  <=  >=`.
- Translates Market Data aggregates into Stock Analysis aggregates through an anti-corruption layer.
- Runs a screen via `ScreeningService`: scores every stock (100 if all criteria pass, else % met), saves it and publishes `ScreeningCompleted` / `StockScored` events.
- Provides in-memory repositories and a synchronous event bus (handler failures are logged and isolated).

## Quick start
```bash
git clone https://github.com/herrrickshaw/stock-screener-ddd.git
cd stock-screener-ddd
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-ddd.txt      # dev tools only; runtime is stdlib
python -m pytest -q
```

```python
from datetime import datetime, timedelta
from decimal import Decimal

from src.market_data.domain.models import OHLC, MarketData, Ticker
from src.market_data.domain.repositories import MarketDataRepositoryMemory
from src.shared.infrastructure.event_bus import EventBus
from src.stock_analysis.application.screening_service import ScreeningService
from src.stock_analysis.domain.models import Criterion, Screen
from src.stock_analysis.domain.repositories import StockRepositoryMemory

md_repo = MarketDataRepositoryMemory()
ohlc = OHLC(Decimal("100"), Decimal("105"), Decimal("95"), Decimal("100"), 1000)
md_repo.save(MarketData(Ticker("INFY", "NSE"), datetime.now() - timedelta(days=1), ohlc,
                        {"PE": Decimal("18"), "ROE": Decimal("25")}))

screen = Screen("Quality", "Low PE, high ROE",
                [Criterion("PE", "<", Decimal("20")), Criterion("ROE", ">", Decimal("15"))])
result = ScreeningService(StockRepositoryMemory(), md_repo, EventBus()).run_screen(screen)
print(result)   # ScreeningResult(Quality: 1/1)
```

## How it works
| Stage | Module | Output |
|---|---|---|
| Market data capture | `src/market_data/domain/models.py` | `MarketData` aggregate (OHLC + metrics) |
| Persistence port | `src/market_data/domain/repositories.py` | `MarketDataRepository` + in-memory impl |
| Translation (ACL) | `src/stock_analysis/infrastructure/market_data_acl.py` | `Stock` aggregate with numeric metrics |
| Screening rules | `src/stock_analysis/domain/models.py` | `Criterion` / `Screen` / `Stock.matches_screen` |
| Orchestration | `src/stock_analysis/application/screening_service.py` | `ScreeningResult`, scores |
| Events | `src/shared/domain/events.py`, `src/shared/infrastructure/event_bus.py` | `ScreeningCompleted`, `StockScored` |

Design notes: business rules live in the aggregates (`Stock.matches_screen`), not in the service;
a metric that is absent fails a criterion rather than being read as zero; exchanges are validated
against an explicit allowlist (`NSE, BSE, NASDAQ, NYSE, EURONEXT, TSE`) in `Ticker`. See
[ARCHITECTURE.md](ARCHITECTURE.md) for the full context map and
[IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md) for phase history.

## Repository layout
| Path | Purpose |
|---|---|
| `src/shared/` | Base classes (`AggregateRoot`, `ValueObject`, `Repository`), domain events, event bus |
| `src/market_data/` | Context 1: market data models and repository port |
| `src/stock_analysis/` | Context 2: screening domain, ACL, application service |
| `src/portfolio_strategy/`, `backtesting/`, `risk_signals/`, `reporting/` | Phases 3-6: empty skeletons |
| `tests/` | `unit/` and `integration/` pytest suites (offline) |
| `notebooks/colab_test.ipynb` | Colab smoke notebook (see [HOW_TO_USE_WITH_AI.md](HOW_TO_USE_WITH_AI.md)) |

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/herrrickshaw/stock-screener-ddd/blob/main/notebooks/colab_test.ipynb)

## Configuration
None. No environment variables, credentials or network access are used.

## Testing
```bash
python -m pytest -q          # 48 tests, offline
ruff check src tests
```
CI (`.github/workflows/ci.yml`) runs lint and tests on Python 3.9 and 3.12.

## Limitations and known issues
- In-memory repositories only; no PostgreSQL, API or market-data adapters yet.
- `StockRepository.find_by_id` and `MarketDataRepositoryMemory.find_by_id` raise `NotImplementedError` (the base `Repository` contract does not fit ticker/date keys).
- `StockScored` events are published only for stocks that pass every criterion, and carry empty `criteria_met` / `criteria_failed` lists.
- The event bus is synchronous and in-process; swap for a broker in production.
- Phases 3-6 are not implemented.

## References
- Evans, E. (2003). *Domain-Driven Design: Tackling Complexity in the Heart of Software*.
- Özkan, B., et al. (2025). *Domain-Driven Design: A Systematic Literature Review*.

## Licence
No licence file yet — all rights reserved.
