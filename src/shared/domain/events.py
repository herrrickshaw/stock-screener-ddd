"""
Shared Domain Events
Published by multiple bounded contexts
"""

from dataclasses import dataclass
from datetime import datetime
from typing import List, Dict, Any
from .base import DomainEvent


@dataclass
class MarketDataFetched(DomainEvent):
    """
    Published by: Market Data Provider Context
    Subscribed to by: Stock Analysis, Portfolio, Backtesting
    """
    ticker: str
    exchange: str
    date: datetime
    ohlc_data: Dict[str, float]
    metrics: Dict[str, float]

    def __post_init__(self):
        super().__init__()


@dataclass
class DataValidationFailed(DomainEvent):
    """Published by: Market Data Provider Context"""
    ticker: str
    date: datetime
    reason: str

    def __post_init__(self):
        super().__init__()


@dataclass
class ScreeningCompleted(DomainEvent):
    """
    Published by: Stock Analysis Context
    Subscribed to by: Portfolio, Backtesting, Reporting, Risk & Signals
    """
    screen_name: str
    stocks_matched: List[str]
    total_evaluated: int
    timestamp: datetime = None

    def __post_init__(self):
        super().__init__()


@dataclass
class StockScored(DomainEvent):
    """Published by: Stock Analysis Context"""
    ticker: str
    screen_name: str
    score: float
    confidence: float
    criteria_met: List[str]
    criteria_failed: List[str]

    def __post_init__(self):
        super().__init__()


@dataclass
class PortfolioRebalanced(DomainEvent):
    """
    Published by: Portfolio Strategy Context
    Subscribed to by: Reporting, Risk & Signals, Backtesting
    """
    portfolio_name: str
    old_allocation: Dict[str, float]
    new_allocation: Dict[str, float]
    timestamp: datetime = None

    def __post_init__(self):
        super().__init__()


@dataclass
class AllocationChanged(DomainEvent):
    """Published by: Portfolio Strategy Context"""
    portfolio_name: str
    ticker: str
    old_weight: float
    new_weight: float

    def __post_init__(self):
        super().__init__()


@dataclass
class BacktestCompleted(DomainEvent):
    """
    Published by: Backtesting Context
    Subscribed to by: Reporting, Risk & Signals
    """
    portfolio_name: str
    start_date: datetime
    end_date: datetime
    total_return: float
    annualized_return: float
    sharpe_ratio: float
    max_drawdown: float

    def __post_init__(self):
        super().__init__()


@dataclass
class PerformanceReport(DomainEvent):
    """Published by: Backtesting Context"""
    portfolio_name: str
    metrics: Dict[str, Any]

    def __post_init__(self):
        super().__init__()


@dataclass
class RiskThresholdExceeded(DomainEvent):
    """
    Published by: Risk & Signals Context
    Subscribed to by: Reporting
    """
    portfolio_name: str
    metric_name: str
    threshold: float
    actual_value: float
    severity: str  # LOW, MEDIUM, HIGH, CRITICAL

    def __post_init__(self):
        super().__init__()


@dataclass
class BuySignalGenerated(DomainEvent):
    """
    Published by: Risk & Signals Context
    Subscribed to by: Reporting
    """
    ticker: str
    confidence: float
    reason: str
    suggested_allocation: float

    def __post_init__(self):
        super().__init__()


@dataclass
class SellSignalGenerated(DomainEvent):
    """Published by: Risk & Signals Context"""
    ticker: str
    confidence: float
    reason: str
    suggested_reduction: float

    def __post_init__(self):
        super().__init__()


@dataclass
class ReportGenerated(DomainEvent):
    """Published by: Reporting Context"""
    report_type: str  # daily, weekly, monthly
    generated_at: datetime
    content_summary: str

    def __post_init__(self):
        super().__init__()


@dataclass
class NotificationSent(DomainEvent):
    """Published by: Reporting Context"""
    recipient: str
    notification_type: str
    subject: str
    timestamp: datetime = None

    def __post_init__(self):
        super().__init__()
