"""Extra unit tests: Price ordering, OHLC bounds, MarketData invariants, MarketCalendar."""
from datetime import date, datetime, timedelta
from decimal import Decimal

import pytest

from src.market_data.domain.models import OHLC, MarketCalendar, MarketData, Metric, Price, Ticker

D = Decimal


class TestTickerBoundaries:
    def test_symbol_of_exactly_ten_chars_is_allowed(self):
        assert Ticker("A" * 10, "NSE").symbol == "A" * 10

    def test_symbol_of_eleven_chars_is_rejected(self):
        with pytest.raises(ValueError, match="Invalid ticker"):
            Ticker("A" * 11, "NSE")

    @pytest.mark.parametrize("ex", ["NSE", "BSE", "NASDAQ", "NYSE", "EURONEXT", "TSE"])
    def test_every_supported_exchange_is_accepted(self, ex):
        assert str(Ticker("X", ex)) == "X." + ex

    def test_unknown_exchange_message_names_it(self):
        with pytest.raises(ValueError, match="Unknown exchange: LSE"):
            Ticker("X", "LSE")

    def test_same_symbol_on_two_exchanges_is_not_equal(self):
        assert Ticker("X", "NSE") != Ticker("X", "BSE")


class TestPriceOrdering:
    def test_default_currency_is_inr(self):
        assert Price(D("1")).currency == "INR"
        assert str(Price(D("1.5"), "USD")) == "1.5 USD"

    def test_negative_rejected_but_tiny_positive_ok(self):
        with pytest.raises(ValueError, match="negative"):
            Price(D("-0.0001"))
        assert Price(D("0.0001")).value == D("0.0001")

    @pytest.mark.parametrize(
        "a,b,lt,le,gt,ge",
        [
            ("1", "2", True, True, False, False),
            ("2", "2", False, True, False, True),
            ("3", "2", False, False, True, True),
        ],
    )
    def test_price_vs_price(self, a, b, lt, le, gt, ge):
        pa, pb = Price(D(a)), Price(D(b))
        assert (pa < pb, pa <= pb, pa > pb, pa >= pb) == (lt, le, gt, ge)

    @pytest.mark.parametrize(
        "a,b,lt,le,gt,ge",
        [
            ("1", "2", True, True, False, False),
            ("2", "2", False, True, False, True),
            ("3", "2", False, False, True, True),
        ],
    )
    def test_price_vs_plain_number(self, a, b, lt, le, gt, ge):
        p, n = Price(D(a)), D(b)
        assert (p < n, p <= n, p > n, p >= n) == (lt, le, gt, ge)

    def test_currency_is_ignored_by_ordering_but_not_by_equality(self):
        assert Price(D("1"), "INR") <= Price(D("1"), "USD")
        assert Price(D("1"), "INR") != Price(D("1"), "USD")


class TestOHLCBoundaries:
    def test_open_and_close_may_sit_exactly_on_the_bounds(self):
        o = OHLC(D("1"), D("2"), D("1"), D("2"), 0)
        assert o.volume == 0

    def test_open_above_high_rejected(self):
        with pytest.raises(ValueError, match="Open"):
            OHLC(D("3"), D("2"), D("1"), D("2"), 1)

    def test_open_below_low_rejected(self):
        with pytest.raises(ValueError, match="Open"):
            OHLC(D("0.5"), D("2"), D("1"), D("1.5"), 1)

    def test_close_above_high_rejected(self):
        with pytest.raises(ValueError, match="Close"):
            OHLC(D("1.5"), D("2"), D("1"), D("3"), 1)

    def test_close_below_low_rejected(self):
        with pytest.raises(ValueError, match="Close"):
            OHLC(D("1.5"), D("2"), D("1"), D("0.5"), 1)

    def test_negative_volume_rejected_zero_ok(self):
        with pytest.raises(ValueError, match="Volume"):
            OHLC(D("1"), D("1"), D("1"), D("1"), -1)


class TestMetric:
    def test_valid(self):
        m = Metric("PE", D("12"), datetime(2024, 1, 1))
        assert m.name == "PE" and m.value == D("12")

    def test_empty_name_rejected(self):
        with pytest.raises(ValueError, match="Metric name required"):
            Metric("", D("1"), datetime(2024, 1, 1))


def _md(days_ago=0.0, hours_ago=0.0, metrics=None):
    p = Price(D("10"))
    when = datetime.now() - timedelta(days=days_ago, hours=hours_ago)
    return MarketData(Ticker("X", "NSE"), when, OHLC(p.value, p.value, p.value, p.value, 5), metrics)


class TestMarketDataInvariants:
    def test_future_date_rejected(self):
        with pytest.raises(ValueError, match="future"):
            _md(days_ago=-1)

    def test_default_metrics_are_not_shared_between_instances(self):
        a, b = _md(), _md()
        a.add_metric("PE", D("1"))
        assert b.metrics == {}

    def test_passed_metrics_dict_is_used(self):
        m = _md(metrics={"PE": D("3")})
        assert m.metrics == {"PE": D("3")}

    def test_empty_dict_metrics_is_replaced_by_a_fresh_one(self):
        given = {}
        m = _md(metrics=given)
        m.add_metric("PE", D("1"))
        assert "PE" in m.metrics
        assert m.metrics is not given and given == {}

    @pytest.mark.parametrize("missing", ["PE", "ROE", "MarketCap"])
    def test_incomplete_if_any_required_metric_is_missing(self, missing):
        full = {"PE": D("1"), "ROE": D("1"), "MarketCap": D("1")}
        del full[missing]
        assert _md(metrics=full).is_complete() is False

    def test_complete_with_extra_metrics(self):
        full = {"PE": D("1"), "ROE": D("1"), "MarketCap": D("1"), "X": D("1")}
        assert _md(metrics=full).is_complete() is True

    def test_empty_is_incomplete(self):
        assert _md().is_complete() is False

    def test_is_stale_boundary_is_strictly_greater_than_threshold(self):
        # age 365d + 1h -> .days == 365 -> not stale; 366d + 1h -> stale
        assert _md(days_ago=365, hours_ago=1).is_stale() is False
        assert _md(days_ago=366, hours_ago=1).is_stale() is True

    def test_is_stale_custom_threshold(self):
        assert _md(days_ago=10, hours_ago=1).is_stale(days_threshold=10) is False
        assert _md(days_ago=11, hours_ago=1).is_stale(days_threshold=10) is True
        assert _md(days_ago=0, hours_ago=1).is_stale(days_threshold=0) is False

    def test_str(self):
        m = _md()
        assert str(m) == "MarketData(X.NSE, %s)" % m.date.date()


class TestMarketCalendar:
    @pytest.fixture
    def cal(self):
        return MarketCalendar("NSE", {0, 1, 2, 3, 4}, {date(2024, 1, 8)})

    def test_weekday_is_trading_day_weekend_is_not(self, cal):
        assert cal.is_trading_day(datetime(2024, 1, 5)) is True    # Friday
        assert cal.is_trading_day(datetime(2024, 1, 6)) is False   # Saturday
        assert cal.is_trading_day(datetime(2024, 1, 7)) is False   # Sunday

    def test_holiday_overrides_weekday(self, cal):
        assert cal.is_trading_day(datetime(2024, 1, 8)) is False   # Monday holiday
        assert cal.is_trading_day(datetime(2024, 1, 8, 15, 30)) is False

    def test_next_trading_day_skips_weekend_and_holiday(self, cal):
        assert cal.next_trading_day(datetime(2024, 1, 5)) == datetime(2024, 1, 9)

    def test_next_trading_day_is_strictly_after(self, cal):
        assert cal.next_trading_day(datetime(2024, 1, 2)) == datetime(2024, 1, 3)

    def test_previous_trading_day_skips_weekend_and_holiday(self, cal):
        assert cal.previous_trading_day(datetime(2024, 1, 9)) == datetime(2024, 1, 5)

    def test_previous_trading_day_is_strictly_before(self, cal):
        assert cal.previous_trading_day(datetime(2024, 1, 3)) == datetime(2024, 1, 2)

    def test_time_of_day_is_preserved(self, cal):
        assert cal.next_trading_day(datetime(2024, 1, 2, 9, 15)) == datetime(2024, 1, 3, 9, 15)

    def test_custom_trading_days(self):
        sat = MarketCalendar("X", {5}, set())
        assert sat.is_trading_day(datetime(2024, 1, 6)) is True
        assert sat.next_trading_day(datetime(2024, 1, 6)) == datetime(2024, 1, 13)
