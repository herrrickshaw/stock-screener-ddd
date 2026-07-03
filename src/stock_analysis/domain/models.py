"""
Stock Analysis Context - Domain Models
Core domain for stock screening and evaluation
"""

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import List, Dict

from src.shared.domain.base import ValueObject, AggregateRoot, DomainException


class ScreeningException(DomainException):
    """Raised when screening operation is invalid"""
    pass


@dataclass(frozen=True)
class Criterion(ValueObject):
    """
    Value Object: A single screening criterion
    Immutable rule for evaluating stocks
    """
    metric_name: str  # "PE", "ROE", "DebtToEquity"
    operator: str  # "<", ">", "=="
    threshold: Decimal

    def __post_init__(self):
        if not self.metric_name:
            raise ValueError("Metric name required")
        if self.operator not in ["<", ">", "==", "<=", ">="]:
            raise ValueError(f"Unknown operator: {self.operator}")

    def matches(self, value: Decimal) -> bool:
        """
        Evaluate if value matches this criterion
        Pure business logic - no side effects
        """
        if self.operator == "<":
            return value < self.threshold
        elif self.operator == ">":
            return value > self.threshold
        elif self.operator == "==":
            return value == self.threshold
        elif self.operator == "<=":
            return value <= self.threshold
        elif self.operator == ">=":
            return value >= self.threshold
        return False

    def __str__(self) -> str:
        return f"{self.metric_name} {self.operator} {self.threshold}"


@dataclass(frozen=True)
class Screen(ValueObject):
    """
    Value Object: Immutable set of screening criteria
    Defines a specific investment screening strategy (e.g., Coffee Can)
    """
    name: str
    description: str
    criteria: List[Criterion] = field(default_factory=list)
    version: int = 1

    def __post_init__(self):
        if not self.name:
            raise ValueError("Screen name required")
        if not self.criteria:
            raise ValueError("Screen must have at least one criterion")

    def __str__(self) -> str:
        return f"Screen({self.name} v{self.version}, {len(self.criteria)} criteria)"


class Stock(AggregateRoot):
    """
    AGGREGATE ROOT: Represents a stock with metrics

    Invariants:
    - Ticker must be unique
    - All metrics must be numeric
    - Fundamentals must be current

    Responsibilities:
    - Store stock data and metrics
    - Evaluate against screens
    - Track screening results
    """

    def __init__(self, ticker: str, exchange: str, metrics: Dict[str, Decimal] = None):
        super().__init__()
        self.ticker = ticker
        self.exchange = exchange
        self.metrics = metrics or {}
        self.screening_results: Dict[str, Dict] = {}
        self.last_updated = datetime.now()

    def add_metric(self, name: str, value: Decimal) -> None:
        """Add or update a metric"""
        if not isinstance(value, Decimal):
            value = Decimal(str(value))
        self.metrics[name] = value
        self.updated_at = datetime.now()

    def get_metric(self, name: str) -> Decimal:
        """Retrieve a metric value"""
        return self.metrics.get(name, Decimal("0"))

    def matches_screen(self, screen: Screen) -> bool:
        """
        Core Business Logic: Evaluate if stock passes all criteria in screen

        This is WHERE THE DOMAIN LOGIC LIVES - not in infrastructure,
        not in application services, but in the aggregate itself.
        """
        for criterion in screen.criteria:
            metric_value = self.get_metric(criterion.metric_name)
            if metric_value == Decimal("0") and criterion.metric_name not in self.metrics:
                # Metric not available
                return False
            if not criterion.matches(metric_value):
                # Failed criterion
                return False
        return True

    def record_screening_result(self, screen: Screen, passed: bool, details: Dict = None) -> None:
        """Record that this stock was evaluated against a screen"""
        self.screening_results[screen.name] = {
            "passed": passed,
            "timestamp": datetime.now(),
            "details": details or {}
        }
        self.updated_at = datetime.now()

    def get_screening_result(self, screen_name: str) -> Dict:
        """Get screening result for a specific screen"""
        return self.screening_results.get(screen_name, {})

    def is_fresh(self, days_threshold: int = 30) -> bool:
        """Check if metrics are current"""
        age_days = (datetime.now() - self.last_updated).days
        return age_days <= days_threshold

    @property
    def pe_ratio(self) -> Decimal:
        """Domain accessor for PE ratio"""
        return self.get_metric("PE")

    @property
    def roe_ratio(self) -> Decimal:
        """Domain accessor for ROE ratio"""
        return self.get_metric("ROE")

    @property
    def debt_to_equity(self) -> Decimal:
        """Domain accessor for debt-to-equity ratio"""
        return self.get_metric("DebtToEquity")

    def __str__(self) -> str:
        return f"Stock({self.ticker}.{self.exchange}, {len(self.metrics)} metrics)"


class StockScore:
    """
    VALUE OBJECT: Represents how well a stock matches a screen
    Used to rank stocks after screening
    """

    def __init__(self, stock_ticker: str, screen_name: str, score: float, criteria_met: int, total_criteria: int):
        self.stock_ticker = stock_ticker
        self.screen_name = screen_name
        self.score = score  # 0-100 percentage
        self.criteria_met = criteria_met
        self.total_criteria = total_criteria

    @property
    def criteria_percentage(self) -> float:
        """What percentage of criteria passed"""
        if self.total_criteria == 0:
            return 0
        return (self.criteria_met / self.total_criteria) * 100

    @property
    def confidence(self) -> float:
        """Confidence level based on criteria met"""
        return self.criteria_percentage / 100

    def __str__(self) -> str:
        return f"StockScore({self.stock_ticker}, {self.score:.1f}%, {self.criteria_met}/{self.total_criteria})"
