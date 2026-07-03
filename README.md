# Stock Screener - Domain-Driven Design Implementation

A clean, modular implementation of a stock screening system using Domain-Driven Design (DDD) principles. Separates domain logic from infrastructure concerns through bounded contexts, anti-corruption layers, and event-driven communication.

## Architecture Overview

### Bounded Contexts

1. **Market Data Context** — Raw OHLC and calculated metrics
2. **Stock Analysis Context** — Screening logic and stock evaluation
3. **Portfolio Strategy** (Phase 3) — Position sizing and rebalancing
4. **Backtesting** (Phase 4) — Historical performance simulation
5. **Risk & Signals** (Phase 5) — Risk monitoring and trading signals
6. **Reporting** (Phase 6) — Results and notifications

### Key Principles

- **Domain-Driven Design**: Business logic lives in domain models, not services
- **Bounded Contexts**: Clear separation of concerns with explicit boundaries
- **Anti-Corruption Layers**: Translate between external formats and domain concepts
- **Value Objects**: Immutable, self-validating domain primitives (Price, Ticker, Criterion)
- **Aggregate Roots**: Consistency boundaries (MarketData, Stock)
- **Domain Events**: Publish-subscribe for decoupled inter-context communication
- **Repository Pattern**: Abstraction between domain and persistence

## Project Structure

```
stock-screener-ddd/
├── src/
│   ├── shared/                          # Shared infrastructure
│   │   ├── domain/
│   │   │   ├── base.py                 # AggregateRoot, ValueObject, Repository
│   │   │   └── events.py               # All domain events
│   │   └── infrastructure/
│   │       └── event_bus.py            # In-process event publishing
│   ├── market_data/                     # Context 1: Market Data
│   │   ├── domain/
│   │   │   ├── models.py               # Ticker, Price, OHLC, MarketData
│   │   │   └── repositories.py         # MarketDataRepository
│   │   └── infrastructure/
│   │       └── ...                     # Future: DB, API adapters
│   └── stock_analysis/                  # Context 2: Stock Analysis
│       ├── domain/
│       │   ├── models.py               # Criterion, Screen, Stock
│       │   └── repositories.py         # StockRepository
│       ├── infrastructure/
│       │   └── market_data_acl.py      # Anti-Corruption Layer
│       └── application/
│           └── screening_service.py    # Orchestration layer
└── tests/
    ├── unit/
    │   └── market_data/
    │       └── test_models.py          # 19 unit tests ✓
    └── integration/
        └── test_stock_analysis_integration.py  # 10 integration tests ✓
```

## Phase Completion Status

### Phase 1: Market Data Context ✓ (Complete)
- Domain models: Ticker, Price, OHLC, Metric, MarketData
- Repository pattern with in-memory implementation
- 19 unit tests passing

### Phase 2: Stock Analysis Context ✓ (Complete)
- Domain models: Criterion, Screen, Stock aggregate, StockScore
- Anti-Corruption Layer translating Market Data → domain objects
- Application Service orchestrating screening operations
- Domain events publishing (ScreeningCompleted, StockScored)
- 10 integration tests passing

### Phase 3: Portfolio Strategy Context (Planned)
- Position sizing and rebalancing logic
- Portfolio aggregate and allocation decisions
- Integration with screening results

### Phase 4: Backtesting Context (Planned)
- Historical data simulation
- Performance metrics calculation
- Walk-forward testing

### Phase 5: Risk & Signals Context (Planned)
- Risk threshold monitoring
- Trading signal generation (buy/sell)
- Correlation and drawdown tracking

### Phase 6: Reporting Context (Planned)
- Daily/weekly/monthly reports
- Multi-channel notifications
- Performance dashboards

## Running Tests

```bash
# All tests
python3 -m pytest tests/ -v

# Phase 1: Market Data unit tests
python3 -m pytest tests/unit/market_data/test_models.py -v

# Phase 2: Stock Analysis integration tests
python3 -m pytest tests/integration/test_stock_analysis_integration.py -v

# With coverage
python3 -m pytest tests/ --cov=src --cov-report=html
```

## Key Design Patterns

### Anti-Corruption Layer (ACL)
Isolates domain logic from external format changes:
```python
# Market Data uses Price value objects
market_data.ohlc.close_price  # → Price(Decimal("1520.00"), "INR")

# Stock Analysis works with raw Decimal metrics
stock.get_metric("Close")     # → Decimal("1520.00")

# ACL handles translation
stock = acl.stock_from_market_data(market_data)  # Translates transparently
```

### Domain Events
Publish-subscribe for zero-coupling communication:
```python
# Stock Analysis publishes when screening completes
event_bus.publish(ScreeningCompleted(
    screen_name="Low PE",
    stocks_matched=["INFY", "TCS"],
    total_evaluated=100
))

# Other contexts subscribe and react (Reporting, Backtesting, etc.)
```

### Repository Pattern
Abstraction layer between domain and persistence:
```python
# Domain doesn't know about storage
class StockRepository(ABC):
    def save(self, stock: Stock) -> None: ...
    def find_by_ticker(self, ticker: str, exchange: str) -> Stock: ...

# Implementations can switch (Memory → DB → API)
stock_repo = StockRepositoryMemory()  # Testing
stock_repo = StockRepositoryPostgres()  # Production
```

## Dependencies

- Python 3.9+
- pytest 7.0+ (testing)
- dataclasses (standard library)
- decimal (standard library)

## Getting Started

```bash
# Clone and setup
git clone <repo-url>
cd stock-screener-ddd

# Install dependencies
pip install -r requirements-ddd.txt

# Run tests to verify
python3 -m pytest tests/ -v

# Run screening
python3 -c "
from src.stock_analysis.application.screening_service import ScreeningService
from src.stock_analysis.domain.models import Criterion, Screen
from decimal import Decimal

# Create screening logic here
"
```

## Next Steps

1. **Phase 3**: Implement Portfolio Strategy context with position sizing
2. **Persistence**: Add PostgreSQL repository implementations
3. **Data Sources**: Integrate yfinance/nsepython for market data
4. **Performance**: Add caching layer for frequently accessed data
5. **Monitoring**: Integrate logging and metrics for production use

## Contributing

This is a reference implementation of DDD principles for stock screening. Key contributions:
- New bounded contexts following the same pattern
- Persistence layer implementations (PostgreSQL, MongoDB, etc.)
- Production event bus (RabbitMQ, Kafka)
- REST API layer for external consumption

## References

- Evans, E. (2003). *Domain-Driven Design: Tackling Complexity in the Heart of Software*
- Özkan, B., et al. (2025). *Domain-Driven Design: A Systematic Literature Review*
- Pattern: Repository, Aggregate, Value Object, Bounded Context
