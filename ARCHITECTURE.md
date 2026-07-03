# Stock Screener DDD - Architecture Documentation

## Executive Summary

This repository implements a Domain-Driven Design (DDD) approach to stock screening. The architecture separates concerns into six bounded contexts, each with its own domain model, repositories, and event publishing. Phase 1 and Phase 2 are complete with full test coverage (29/29 tests passing).

## Core DDD Concepts Used

### 1. Bounded Contexts
Distinct subdomains with their own ubiquitous language and business rules:
- **Market Data**: Raw price data and calculated metrics
- **Stock Analysis**: Screening logic and stock evaluation
- **Portfolio Strategy**: Position sizing and rebalancing
- **Backtesting**: Historical simulation
- **Risk & Signals**: Risk monitoring and trading signals
- **Reporting**: Results aggregation and distribution

### 2. Value Objects
Immutable, self-validating domain concepts:
- **Price**: Amount + currency, always non-negative
- **Ticker**: Symbol + exchange, validated format
- **OHLC**: Open, high, low, close prices + volume
- **Criterion**: Metric name + operator + threshold
- **Screen**: Named set of criteria for evaluation
- **StockScore**: Score from screening evaluation

### 3. Aggregate Roots
Consistency boundaries that protect invariants:
- **MarketData**: Owns ticker, OHLC, metrics, fetched_at
  - Invariant: fetched_at ≤ now
  - Responsibility: Store raw market data
- **Stock**: Owns ticker, exchange, metrics, screening results
  - Invariant: All metrics must be Decimal
  - Responsibility: Evaluate against screens, track results

### 4. Repositories
Abstraction between domain and persistence:
```python
class MarketDataRepository(ABC):
    def save(market_data: MarketData) -> None
    def find_by_ticker_and_date(ticker: Ticker, date: datetime) -> Optional[MarketData]
    def find_by_ticker(ticker: Ticker, days: int = 252) -> List[MarketData]
    def find_all() -> List[MarketData]
    def delete(ticker: Ticker, date: datetime) -> None
```

### 5. Application Services
Thin orchestration layer:
- Load aggregates from repositories
- Call domain logic (methods on aggregates)
- Save results back to repositories
- Publish domain events

Example: `ScreeningService.run_screen()`
```python
def run_screen(screen: Screen) -> ScreeningResult:
    stocks = self.load_stocks_from_market_data()
    for stock in stocks:
        passed = stock.matches_screen(screen)  # ← DOMAIN LOGIC
        stock.record_screening_result(screen, passed)
    self.stock_repo.save_all(stocks)
    self.event_bus.publish(ScreeningCompleted(...))
```

### 6. Domain Events
Publish-subscribe for decoupled communication between contexts:
- **MarketDataFetched**: New market data available
- **ScreeningCompleted**: Screening operation finished
- **StockScored**: Individual stock evaluation result
- **PortfolioRebalanced**: Position adjustments made
- **BacktestCompleted**: Historical simulation done
- **RiskThresholdExceeded**: Risk limit breached
- **BuySignalGenerated** / **SellSignalGenerated**: Trading signals
- **ReportGenerated**: Results ready for distribution

### 7. Anti-Corruption Layers (ACLs)
Translate between external formats and domain concepts:

**Example**: Market Data → Stock Analysis
```python
class MarketDataACL:
    @staticmethod
    def stock_from_market_data(market_data: MarketData) -> Stock:
        # Extracts Decimal from Price objects
        stock.add_metric("Close", market_data.ohlc.close_price.value)
        # Normalizes metrics from Market Data format
        stock.add_metric("PE", market_data.metrics["PE"])
        return stock
```

**Why it matters**: If Market Data changes from using Price objects to using raw floats, only the ACL changes. Stock Analysis is completely isolated.

---

## Phase 1: Market Data Context

### Models (`src/market_data/domain/models.py`)

#### Value Objects

**Ticker(symbol: str, exchange: str)**
- Validates: symbol length 1-10, exchange in known set
- Exchanges: NSE, BSE, NASDAQ, NYSE, EURONEXT, TSE
- Immutable, comparable, hashable

**Price(value: Decimal, currency: str = "INR")**
- Validates: value ≥ 0
- Immutable, comparable with other Prices
- Implements `__le__`, `__lt__`, `__ge__`, `__gt__` for OHLC range checking

**OHLC(open_price, high_price, low_price, close_price, volume)**
- Validates:
  - low_price ≤ open_price ≤ high_price
  - low_price ≤ close_price ≤ high_price
  - volume ≥ 0
- Immutable, represents one trading day

**Metric(name: str, value: Decimal, as_of_date: datetime)**
- Named financial metrics (PE, ROE, DebtToEquity, etc.)
- Timestamp for metric currency

#### Aggregate Roots

**MarketData(ticker, date, ohlc, metrics)**
- Owns OHLC and calculated metrics
- Methods:
  - `add_metric(name, value)`: Add financial metric
  - `get_metric(name)`: Retrieve metric value
  - `is_complete()`: Has essential metrics? (PE, ROE, MarketCap)
  - `is_stale(days_threshold)`: Data older than threshold?
- Invariants:
  - date ≤ fetched_at
  - OHLC must be valid
  - All metrics must be Decimal

### Repositories (`src/market_data/domain/repositories.py`)

```python
class MarketDataRepository(ABC):
    @abstractmethod
    def save(market_data: MarketData) -> None
    @abstractmethod
    def find_by_ticker_and_date(ticker: Ticker, date: datetime) -> Optional[MarketData]
    @abstractmethod
    def find_by_ticker(ticker: Ticker, days: int = 252) -> List[MarketData]
    @abstractmethod
    def find_all() -> List[MarketData]
    @abstractmethod
    def delete(ticker: Ticker, date: datetime) -> None
```

**MarketDataRepositoryMemory**: In-memory testing implementation using dict

### Tests: 19 unit tests (all passing)

```
TestTicker (6 tests)
  ✓ Create valid ticker
  ✓ Empty symbol validation
  ✓ Too-long symbol validation
  ✓ Unknown exchange validation
  ✓ Equality comparison
  ✓ String representation

TestPrice (3 tests)
  ✓ Create valid price
  ✓ Negative price validation
  ✓ Zero price allowed

TestOHLC (4 tests)
  ✓ Create valid OHLC
  ✓ Open outside range validation
  ✓ Close outside range validation
  ✓ Negative volume validation

TestMarketData (6 tests)
  ✓ Create valid market data
  ✓ Add and retrieve metrics
  ✓ is_complete() with required metrics
  ✓ is_complete() without required metrics
  ✓ is_stale() for recent data
  ✓ String representation
```

---

## Phase 2: Stock Analysis Context

### Models (`src/stock_analysis/domain/models.py`)

#### Value Objects

**Criterion(metric_name: str, operator: str, threshold: Decimal)**
- Validates: operator in {<, >, ==, <=, >=}
- Method: `matches(value: Decimal) -> bool`
- Example: `Criterion("PE", "<", Decimal("30"))`

**Screen(name: str, description: str, criteria: List[Criterion], version: int = 1)**
- Immutable set of criteria
- Validates: name and criteria non-empty
- Example: Coffee Can screen with PE < 30, ROE > 15

**StockScore(stock_ticker, screen_name, score, criteria_met, total_criteria)**
- Represents how well a stock matched a screen
- Properties:
  - `criteria_percentage`: % of criteria met
  - `confidence`: 0-1 confidence level
  - `score`: 0-100 percentage

#### Aggregate Roots

**Stock(ticker: str, exchange: str, metrics: Dict[str, Decimal])**
- Core business logic: evaluating against screens
- Methods:
  - `add_metric(name, value)`: Add or update metric
  - `get_metric(name)`: Retrieve metric value
  - `matches_screen(screen) -> bool`: **Core business logic**
    - Evaluates all criteria in screen
    - Returns True only if ALL criteria pass
  - `record_screening_result(screen, passed, details)`: Track evaluation
  - `get_screening_result(screen_name)`: Retrieve past results
  - `is_fresh(days_threshold)`: Metrics up to date?
- Properties: `pe_ratio`, `roe_ratio`, `debt_to_equity` accessors
- Invariants:
  - ticker and exchange must be valid
  - All metrics must be non-negative Decimal
  - Screening results immutably recorded

### Anti-Corruption Layer (`src/stock_analysis/infrastructure/market_data_acl.py`)

Translates Market Data (Price objects) → Stock Analysis (Decimal metrics):

```python
class MarketDataACL:
    @staticmethod
    def stock_from_market_data(market_data: MarketData) -> Stock:
        stock = Stock(ticker=market_data.ticker.symbol, exchange=market_data.ticker.exchange)
        
        # Extract Decimal from Price objects
        stock.add_metric("Open", market_data.ohlc.open_price.value)
        stock.add_metric("High", market_data.ohlc.high_price.value)
        stock.add_metric("Low", market_data.ohlc.low_price.value)
        stock.add_metric("Close", market_data.ohlc.close_price.value)
        stock.add_metric("Volume", Decimal(market_data.ohlc.volume))
        
        # Add financial metrics
        for metric_name, value in market_data.metrics.items():
            stock.add_metric(metric_name, value)
        
        return stock
```

**Key Design**: If Market Data format changes (Price → raw float), only this layer changes. Stock Analysis business logic is isolated.

### Application Service (`src/stock_analysis/application/screening_service.py`)

**ScreeningService**: Orchestrates screening operation

```python
class ScreeningService:
    def __init__(self, stock_repo, market_data_repo, event_bus):
        self.stock_repo = stock_repo
        self.market_data_repo = market_data_repo
        self.event_bus = event_bus
        self.acl = MarketDataACL()
    
    def run_screen(self, screen: Screen) -> ScreeningResult:
        # 1. Load aggregates
        stocks = self.load_stocks_from_market_data()
        
        # 2. Apply domain logic
        for stock in stocks:
            passed = stock.matches_screen(screen)
            stock.record_screening_result(screen, passed)
        
        # 3. Save results
        for stock in stocks:
            self.stock_repo.save(stock)
        
        # 4. Publish events
        self.event_bus.publish(ScreeningCompleted(...))
```

### Repositories (`src/stock_analysis/domain/repositories.py`)

```python
class StockRepository(ABC):
    @abstractmethod
    def save(stock: Stock) -> None
    @abstractmethod
    def find_by_ticker(ticker: str, exchange: str) -> Optional[Stock]
    @abstractmethod
    def find_all() -> List[Stock]
    @abstractmethod
    def delete(ticker: str, exchange: str) -> None
```

### Tests: 10 integration tests (all passing)

```
TestACLTranslation (3 tests)
  ✓ Transform Market Data → Stock
  ✓ Preserve full OHLC data
  ✓ External format change isolation

TestScreeningService (6 tests)
  ✓ Load stocks from market data
  ✓ Full matching (all criteria met)
  ✓ Partial matching (some criteria met)
  ✓ Publish domain events
  ✓ Save results to repository
  ✓ Multiple criteria evaluation

TestContextBoundary (1 test)
  ✓ Market Data format changes isolated to ACL
```

---

## Event-Driven Communication

### Event Bus (`src/shared/infrastructure/event_bus.py`)

In-process pub/sub implementation:

```python
class EventBus:
    def subscribe(event_type, handler) -> None
    def publish(event: DomainEvent) -> None
    def get_event_history() -> List[DomainEvent]
    def get_subscriber_count(event_type) -> int
```

**Design Note**: This is v1 (in-process). Production would use RabbitMQ, Kafka, or AWS SNS/SQS.

### Domain Events (`src/shared/domain/events.py`)

All inherit from `DomainEvent` (base class with timestamp, event_id):

1. **MarketDataFetched** → Published by Market Data context
2. **DataValidationFailed** → Validation errors
3. **ScreeningCompleted** → Published by Stock Analysis context
   - `screen_name`: Which screen ran
   - `stocks_matched`: List of ticker symbols that passed
   - `total_evaluated`: Total stocks evaluated
4. **StockScored** → Individual stock result
5. **PortfolioRebalanced** → Published by Portfolio Strategy
6. **AllocationChanged** → Position weight changes
7. **BacktestCompleted** → Published by Backtesting context
8. **PerformanceReport** → Metrics aggregation
9. **RiskThresholdExceeded** → Published by Risk & Signals
10. **BuySignalGenerated** / **SellSignalGenerated** → Trading signals
11. **ReportGenerated** → Published by Reporting
12. **NotificationSent** → Distribution confirmation

---

## Shared Infrastructure (`src/shared/domain/base.py`)

### Base Classes

**DomainEvent**
```python
class DomainEvent:
    timestamp: datetime  # Auto-set on creation
    event_id: str       # UUID, unique per event
```

**AggregateRoot**
```python
class AggregateRoot:
    id: str                              # UUID
    created_at: datetime
    updated_at: datetime
    domain_events: List[DomainEvent]
    
    def add_domain_event(event)
    def clear_domain_events() -> List[DomainEvent]
```

**ValueObject**
```python
class ValueObject:
    def __eq__(other) -> bool           # Structural equality
    def __hash__() -> int               # By value, not reference
```

**Repository(ABC)**
```python
class Repository(ABC):
    def save(aggregate) -> None
    def find_by_id(id) -> Aggregate
    def find_all() -> List[Aggregate]
    def delete(id) -> None
```

**ApplicationService(ABC)**
```python
class ApplicationService(ABC):
    def execute(*args, **kwargs) -> Any
```

---

## Design Patterns & Decisions

### Why Separate Repositories for Each Context?

Each context has its own repository interface:
- **Market Data**: Queries by ticker + date
- **Stock Analysis**: Queries by ticker + exchange
- **Portfolio**: Queries by portfolio name

This reflects each context's specific access patterns and data needs.

### Why Anti-Corruption Layers?

External systems change format, but domain logic shouldn't break:

| Change | Without ACL | With ACL |
|--------|-------------|----------|
| Price objects → floats | Stock Analysis breaks | Only ACL changes |
| PE ratio → P/E Ratio | Tests fail | Zero impact |
| New metric added | Scattered everywhere | One place in ACL |

### Why Value Objects?

- **Type Safety**: `Decimal` looks like `Decimal`, but `Price` is explicit
- **Validation**: Can't create invalid Ticker("", "NSE")
- **Immutability**: Prevents accidental mutations
- **Equality**: Compared by value, not reference

### Why Aggregate Roots?

- **Consistency**: All invariants enforced in one place
- **Transactions**: Save/load as atomic unit
- **Boundaries**: Clear what's inside vs outside
- **Testing**: Can test aggregate logic without loading related aggregates

---

## Development Workflow

### Adding a New Screen

```python
from decimal import Decimal
from src.stock_analysis.domain.models import Criterion, Screen

# Define criteria
pe_criterion = Criterion("PE", "<", Decimal("30"))
roe_criterion = Criterion("ROE", ">", Decimal("15"))

# Create screen
coffee_can = Screen(
    name="Coffee Can",
    description="Value + quality: Low PE, high ROE",
    criteria=[pe_criterion, roe_criterion]
)

# Run screening
result = screening_service.run_screen(coffee_can)
```

### Implementing a New Context

1. **Define Domain Models** in `domain/models.py`
   - Value objects (immutable)
   - Aggregate roots (with business logic)

2. **Define Repository Interface** in `domain/repositories.py`
   - Abstract methods for persistence

3. **Create Application Service** in `application/service.py`
   - Orchestrate domain logic
   - Publish events

4. **Add ACL** in `infrastructure/acl.py` (if consuming other contexts)
   - Translate external format to domain

5. **Write Tests** in `tests/`
   - Unit tests for models (domain logic)
   - Integration tests for services (context interaction)

---

## Future Phases

### Phase 3: Portfolio Strategy Context (Planned)
- **Models**: Portfolio aggregate, Position value object
- **Logic**: Optimal allocation, rebalancing rules
- **Events**: PortfolioRebalanced, AllocationChanged
- **Integration**: Subscribe to ScreeningCompleted events

### Phase 4: Backtesting Context (Planned)
- **Models**: Backtest aggregate, TradingResult value object
- **Logic**: Replay historical prices, simulate trading
- **Events**: BacktestCompleted, PerformanceReport
- **Integration**: Subscribe to PortfolioRebalanced events

### Phase 5: Risk & Signals Context (Planned)
- **Models**: Portfolio aggregate, Signal value object
- **Logic**: Risk monitoring, signal generation
- **Events**: RiskThresholdExceeded, BuySignalGenerated, SellSignalGenerated
- **Integration**: Subscribe to PortfolioRebalanced, BacktestCompleted

### Phase 6: Reporting Context (Planned)
- **Models**: Report aggregate, Notification value object
- **Logic**: Aggregate results, format reports
- **Events**: ReportGenerated, NotificationSent
- **Integration**: Subscribe to all other contexts

---

## Testing Strategy

### Unit Tests (Test Domain Logic in Isolation)
- Location: `tests/unit/`
- Test Value Objects: Validation, equality, immutability
- Test Aggregates: Methods, invariants, state transitions
- Example: `TestTicker`, `TestPrice`, `TestOHLC`, `TestMarketData`

### Integration Tests (Test Context Interaction)
- Location: `tests/integration/`
- Test ACL: External format translation
- Test Application Service: End-to-end workflows
- Test Event Publishing: Cross-context communication
- Example: `TestScreeningService`, `TestContextBoundary`

### Coverage Target: 80%+

### Running Tests
```bash
# All tests
python3 -m pytest tests/ -v

# Unit only
python3 -m pytest tests/unit/ -v

# Integration only
python3 -m pytest tests/integration/ -v

# With coverage
python3 -m pytest tests/ --cov=src --cov-report=html
```

---

## Key Files Reference

| File | Purpose | Tests |
|------|---------|-------|
| `src/shared/domain/base.py` | Base classes (AggregateRoot, ValueObject, Repository) | — |
| `src/shared/domain/events.py` | All domain events | — |
| `src/shared/infrastructure/event_bus.py` | Event publishing | — |
| `src/market_data/domain/models.py` | Market Data domain (Ticker, Price, OHLC, MarketData) | 19 ✓ |
| `src/market_data/domain/repositories.py` | MarketDataRepository interface | 19 ✓ |
| `src/stock_analysis/domain/models.py` | Stock Analysis domain (Criterion, Screen, Stock) | 10 ✓ |
| `src/stock_analysis/domain/repositories.py` | StockRepository interface | 10 ✓ |
| `src/stock_analysis/infrastructure/market_data_acl.py` | Market Data → Stock Analysis translation | 10 ✓ |
| `src/stock_analysis/application/screening_service.py` | Screening orchestration service | 10 ✓ |

---

## References

- Evans, E. (2003). *Domain-Driven Design: Tackling Complexity in the Heart of Software*. Addison-Wesley.
- Özkan, B., et al. (2025). *Domain-Driven Design: A Systematic Literature Review*. IEEE Transactions on Software Engineering.
- Martin, R. (2017). *Clean Architecture: A Craftsman's Guide to Software Structure and Design*. Prentice Hall.
- Pattern Catalog: Repository, Aggregate, Value Object, Bounded Context, Anti-Corruption Layer
