"""Unit tests for the Stock Analysis domain: Criterion, Screen, Stock, StockScore."""
from datetime import datetime, timedelta
from decimal import Decimal

import pytest

from src.stock_analysis.domain.models import Criterion, Screen, Stock, StockScore

D = Decimal


class TestCriterion:
    @pytest.mark.parametrize("op,value,expected", [
        ("<", "9.99", True), ("<", "10", False),
        (">", "10.01", True), (">", "10", False),
        ("<=", "10", True), ("<=", "10.01", False),
        (">=", "10", True), (">=", "9.99", False),
        ("==", "10", True), ("==", "10.0001", False),
    ])
    def test_operators_at_the_boundary(self, op, value, expected):
        assert Criterion("PE", op, D("10")).matches(D(value)) is expected

    def test_unknown_operator_rejected(self):
        with pytest.raises(ValueError):
            Criterion("PE", "!=", D("10"))

    def test_empty_metric_name_rejected(self):
        with pytest.raises(ValueError):
            Criterion("", "<", D("10"))

    def test_str(self):
        assert str(Criterion("ROE", ">", D("15"))) == "ROE > 15"


class TestScreen:
    def test_requires_name_and_criteria(self):
        with pytest.raises(ValueError):
            Screen("", "d", [Criterion("PE", "<", D("20"))])
        with pytest.raises(ValueError):
            Screen("x", "d", [])

    def test_str_reports_version_and_count(self):
        s = Screen("Value", "d", [Criterion("PE", "<", D("20"))], version=2)
        assert str(s) == "Screen(Value v2, 1 criteria)"


class TestStock:
    def screen(self, *crit):
        return Screen("S", "d", list(crit))

    def test_add_metric_coerces_float_via_str_exactly(self):
        s = Stock("INFY", "NSE")
        s.add_metric("PE", 0.1)
        assert s.metrics["PE"] == D("0.1")          # not 0.1000000000000000055...

    def test_missing_metric_fails_screen_even_if_zero_would_pass(self):
        s = Stock("INFY", "NSE", {"PE": D("15")})
        assert not s.matches_screen(self.screen(Criterion("DebtToEquity", "<", D("1"))))

    def test_real_zero_metric_is_evaluated_not_treated_as_missing(self):
        s = Stock("INFY", "NSE", {"DebtToEquity": D("0")})
        assert s.matches_screen(self.screen(Criterion("DebtToEquity", "<", D("1"))))

    def test_all_criteria_must_pass(self):
        s = Stock("INFY", "NSE", {"PE": D("15"), "ROE": D("12")})
        crit = (Criterion("PE", "<", D("20")), Criterion("ROE", ">", D("15")))
        assert not s.matches_screen(self.screen(*crit))
        s.add_metric("ROE", D("16"))
        assert s.matches_screen(self.screen(*crit))

    def test_record_and_get_screening_result(self):
        s = Stock("INFY", "NSE", {"PE": D("15")})
        scr = self.screen(Criterion("PE", "<", D("20")))
        s.record_screening_result(scr, True, {"k": 1})
        r = s.get_screening_result("S")
        assert r["passed"] is True and r["details"] == {"k": 1}
        assert s.get_screening_result("missing") == {}

    def test_is_fresh_threshold(self):
        s = Stock("INFY", "NSE")
        s.last_updated = datetime.now() - timedelta(days=30)
        assert s.is_fresh(30)
        s.last_updated = datetime.now() - timedelta(days=31)
        assert not s.is_fresh(30)

    def test_domain_accessors(self):
        s = Stock("INFY", "NSE", {"PE": D("15"), "ROE": D("20"), "DebtToEquity": D("0.3")})
        assert (s.pe_ratio, s.roe_ratio, s.debt_to_equity) == (D("15"), D("20"), D("0.3"))


class TestStockScore:
    def test_percentage_and_confidence(self):
        sc = StockScore("INFY", "S", 50.0, 1, 2)
        assert sc.criteria_percentage == 50.0 and sc.confidence == 0.5

    def test_zero_criteria_is_zero_not_division_error(self):
        assert StockScore("INFY", "S", 0.0, 0, 0).criteria_percentage == 0
