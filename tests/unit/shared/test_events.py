"""Tests for shared domain events: construction, identity and field wiring."""
from datetime import datetime
from decimal import Decimal  # noqa: F401

import pytest

from src.shared.domain import events as ev
from src.shared.domain.base import DomainEvent

NOW = datetime(2024, 1, 2, 3, 4, 5)

CASES = [
    (ev.MarketDataFetched, dict(ticker="X", exchange="NSE", date=NOW, ohlc_data={"c": 1.0}, metrics={"PE": 2.0})),
    (ev.DataValidationFailed, dict(ticker="X", date=NOW, reason="bad")),
    (ev.ScreeningCompleted, dict(screen_name="s", stocks_matched=["X"], total_evaluated=3)),
    (ev.StockScored, dict(ticker="X", screen_name="s", score=1.0, confidence=.5,
                          criteria_met=["a"], criteria_failed=["b"])),
    (ev.PortfolioRebalanced, dict(portfolio_name="p", old_allocation={"X": 1.0}, new_allocation={"Y": 1.0})),
    (ev.AllocationChanged, dict(portfolio_name="p", ticker="X", old_weight=.1, new_weight=.2)),
    (ev.BacktestCompleted, dict(portfolio_name="p", start_date=NOW, end_date=NOW, total_return=.1,
                                annualized_return=.2, sharpe_ratio=1.0, max_drawdown=-.3)),
    (ev.PerformanceReport, dict(portfolio_name="p", metrics={"a": 1})),
    (ev.RiskThresholdExceeded, dict(portfolio_name="p", metric_name="var", threshold=1.0,
                                    actual_value=2.0, severity="HIGH")),
    (ev.BuySignalGenerated, dict(ticker="X", confidence=.9, reason="r", suggested_allocation=.1)),
    (ev.SellSignalGenerated, dict(ticker="X", confidence=.9, reason="r", suggested_reduction=.1)),
    (ev.ReportGenerated, dict(report_type="daily", generated_at=NOW, content_summary="s")),
    (ev.NotificationSent, dict(recipient="a", notification_type="mail", subject="s")),
]


@pytest.mark.parametrize("cls,kwargs", CASES, ids=[c.__name__ for c, _ in CASES])
def test_event_is_a_domain_event_with_identity_and_fields(cls, kwargs):
    e = cls(**kwargs)
    assert isinstance(e, DomainEvent)
    assert isinstance(e.timestamp, datetime) and isinstance(e.event_id, str)
    for k, v in kwargs.items():
        assert getattr(e, k) == v
    assert cls(**kwargs).event_id != e.event_id


@pytest.mark.parametrize("cls,kwargs", CASES, ids=[c.__name__ for c, _ in CASES])
def test_missing_required_field_is_rejected(cls, kwargs):
    first = next(iter(kwargs))
    bad = {k: v for k, v in kwargs.items() if k != first}
    with pytest.raises(TypeError):
        cls(**bad)


def test_event_timestamp_is_assigned_at_creation_not_taken_from_field_default():
    # ScreeningCompleted declares timestamp=None as a dataclass default, but __post_init__
    # re-runs DomainEvent.__init__ so the instance always carries a real datetime.
    e = ev.ScreeningCompleted("s", [], 0)
    assert isinstance(e.timestamp, datetime)
    e2 = ev.NotificationSent("a", "t", "s")
    assert isinstance(e2.timestamp, datetime)
