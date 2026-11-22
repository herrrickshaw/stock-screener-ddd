"""Extra tests: Criterion fallthrough, Screen equality, StockScore, ScreeningResult formatting."""
from datetime import datetime, timedelta
from decimal import Decimal

import pytest

from src.shared.domain.base import DomainException
from src.stock_analysis.application.screening_service import ScreeningResult
from src.stock_analysis.domain.models import (
    Criterion,
    Screen,
    ScreeningException,
    Stock,
    StockScore,
)

D = Decimal


def test_criterion_unreachable_fallthrough_returns_false():
    c = Criterion("PE", "<", D("1"))
    object.__setattr__(c, "operator", "!=")  # bypass the frozen validation
    assert c.matches(D("0")) is False


def test_criterion_is_immutable_and_hashable():
    c = Criterion("PE", "<", D("1"))
    with pytest.raises(Exception):
        c.threshold = D("2")
    assert c == Criterion("PE", "<", D("1")) and hash(c) == hash(Criterion("PE", "<", D("1")))
    assert c != Criterion("PE", "<=", D("1"))


def test_screening_exception_is_domain_exception():
    assert issubclass(ScreeningException, DomainException)


def test_screen_equality_and_defaults():
    c = Criterion("PE", "<", D("1"))
    assert Screen("s", "d", [c]) == Screen("s", "d", [c])
    assert Screen("s", "d", [c]).version == 1
    assert Screen("s", "d", [c], version=2) != Screen("s", "d", [c])
    assert str(Screen("s", "d", [c, c], version=3)) == "Screen(s v3, 2 criteria)"


def test_stock_defaults_and_str():
    s = Stock("A", "NSE")
    assert s.metrics == {} and s.screening_results == {}
    assert str(s) == "Stock(A.NSE, 0 metrics)"
    s.add_metric("PE", 3)
    assert s.metrics["PE"] == D("3") and str(s) == "Stock(A.NSE, 1 metrics)"


def test_stocks_do_not_share_default_metrics():
    a, b = Stock("A", "NSE"), Stock("B", "NSE")
    a.add_metric("PE", 1)
    assert b.metrics == {}


def test_add_metric_updates_updated_at():
    s = Stock("A", "NSE")
    before = s.updated_at
    s.add_metric("PE", 1)
    assert s.updated_at >= before


def test_get_screening_result_unknown_is_empty_dict():
    assert Stock("A", "NSE").get_screening_result("nope") == {}


def test_record_result_defaults_details_and_keeps_given():
    s = Stock("A", "NSE")
    scr = Screen("s", "d", [Criterion("PE", "<", D("1"))])
    s.record_screening_result(scr, True)
    assert s.get_screening_result("s")["details"] == {}
    s.record_screening_result(scr, False, {"why": 1})
    r = s.get_screening_result("s")
    assert r["passed"] is False and r["details"] == {"why": 1}


def test_is_fresh_boundary_inclusive():
    s = Stock("A", "NSE")
    s.last_updated = datetime.now() - timedelta(days=30, hours=1)
    assert s.is_fresh() is True            # .days == 30 -> <= 30
    s.last_updated = datetime.now() - timedelta(days=31, hours=1)
    assert s.is_fresh() is False
    assert s.is_fresh(days_threshold=60) is True


def test_debt_to_equity_accessor_and_default_zero():
    s = Stock("A", "NSE", {"DebtToEquity": D("0.4")})
    assert s.debt_to_equity == D("0.4")
    assert Stock("B", "NSE").debt_to_equity == D("0")


def test_stock_score_str_and_fields():
    sc = StockScore("A", "s", 66.666, 2, 3)
    assert str(sc) == "StockScore(A, 66.7%, 2/3)"
    assert sc.criteria_percentage == pytest.approx(66.6667, abs=1e-3)
    assert sc.confidence == pytest.approx(2 / 3)


def test_stock_score_zero_criteria_confidence_is_zero():
    assert StockScore("A", "s", 0, 0, 0).confidence == 0


def test_screening_result_str_and_percentage():
    scr = Screen("alpha", "d", [Criterion("PE", "<", D("1"))])
    r = ScreeningResult(scr, [Stock("A", "NSE")], [], 4)
    assert str(r) == "ScreeningResult(alpha: 1/4)"
    assert r.match_percentage == 25
    assert ScreeningResult(scr, [], [], 0).match_percentage == 0
