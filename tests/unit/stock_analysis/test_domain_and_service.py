"""Characterisation tests for the Stock Analysis context (no network, in-memory repos)."""

from datetime import datetime, timedelta
from decimal import Decimal

import pytest

from src.market_data.domain.models import OHLC, MarketData, Price, Ticker
from src.market_data.domain.repositories import MarketDataRepositoryMemory
from src.shared.domain.events import ScreeningCompleted, StockScored
from src.shared.infrastructure.event_bus import EventBus, get_event_bus, reset_event_bus
from src.stock_analysis.application.screening_service import ScreeningService
from src.stock_analysis.domain.models import Criterion, Screen, Stock
from src.stock_analysis.domain.repositories import StockRepositoryMemory
from src.stock_analysis.infrastructure.market_data_acl import MarketDataACL

YESTERDAY = datetime.now() - timedelta(days=1)


def _market_data(symbol, exchange, metrics, close="100"):
    c = Decimal(close)
    ohlc = OHLC(c, c + 5, c - 5, c, 1000)
    return MarketData(Ticker(symbol, exchange), YESTERDAY, ohlc, dict(metrics))


@pytest.mark.parametrize(
    "op,value,expected",
    [
        ("<", "9", True), ("<", "10", False),
        (">", "11", True), (">", "10", False),
        ("==", "10", True), ("==", "11", False),
        ("<=", "10", True), ("<=", "11", False),
        (">=", "10", True), (">=", "9", False),
    ],
)
def test_criterion_operators(op, value, expected):
    assert Criterion("PE", op, Decimal("10")).matches(Decimal(value)) is expected


def test_criterion_rejects_bad_input():
    with pytest.raises(ValueError):
        Criterion("", "<", Decimal("1"))
    with pytest.raises(ValueError):
        Criterion("PE", "!=", Decimal("1"))


def test_screen_requires_name_and_criteria():
    with pytest.raises(ValueError):
        Screen("", "d", [Criterion("PE", "<", Decimal("1"))])
    with pytest.raises(ValueError):
        Screen("x", "d", [])


def test_missing_metric_fails_screen_even_if_zero_would_pass():
    stock = Stock("AAA", "NSE")
    screen = Screen("s", "d", [Criterion("PE", "<", Decimal("10"))])
    assert stock.matches_screen(screen) is False
    stock.add_metric("PE", 0)
    assert stock.matches_screen(screen) is True


def test_acl_maps_ohlc_and_metrics():
    md = _market_data("INFY", "NSE", {"PE": Decimal("20")}, close="1500")
    stock = MarketDataACL.stock_from_market_data(md)
    assert (stock.ticker, stock.exchange) == ("INFY", "NSE")
    assert stock.get_metric("Close") == Decimal("1500")
    assert stock.get_metric("High") == Decimal("1505")
    assert stock.get_metric("Volume") == Decimal("1000")
    assert stock.get_metric("PE") == Decimal("20")
    assert stock.last_updated == md.fetched_at


def test_acl_accepts_price_value_objects():
    ohlc = OHLC(Price(Decimal("9")), Price(Decimal("11")), Price(Decimal("8")), Price(Decimal("10")), 5)
    md = MarketData(Ticker("TCS", "NSE"), YESTERDAY, ohlc)
    assert MarketDataACL.stock_from_market_data(md).get_metric("Close") == Decimal("10")


def test_acl_extract_metrics_defaults_and_exchange_map():
    md = _market_data("TCS", "NSE", {"PE": Decimal("5")})
    out = MarketDataACL.extract_metrics(md)
    assert out["PE"] == Decimal("5") and out["ROE"] == Decimal("0") and len(out) == 6
    assert MarketDataACL.map_exchange("NSE") == "NSE"
    assert MarketDataACL.map_exchange("XYZ") == "XYZ"


def test_screening_service_scores_and_events():
    mdr, sr, bus = MarketDataRepositoryMemory(), StockRepositoryMemory(), EventBus()
    mdr.save(_market_data("GOOD", "NSE", {"PE": Decimal("10"), "ROE": Decimal("25")}))
    mdr.save(_market_data("HALF", "NSE", {"PE": Decimal("10"), "ROE": Decimal("5")}))
    mdr.save(_market_data("NONE", "NSE", {"PE": Decimal("50"), "ROE": Decimal("5")}))
    screen = Screen("q", "d", [Criterion("PE", "<", Decimal("20")), Criterion("ROE", ">", Decimal("15"))])

    result = ScreeningService(sr, mdr, bus).run_screen(screen)

    assert result.total_evaluated == 3
    assert [s.ticker for s in result.matched_stocks] == ["GOOD"]
    scores = {s.stock_ticker: (s.score, s.criteria_met, s.total_criteria) for s in result.stock_scores}
    assert scores == {"GOOD": (100.0, 2, 2), "HALF": (50.0, 1, 2), "NONE": (0.0, 0, 2)}
    assert result.match_percentage == pytest.approx(100 / 3)
    assert len(sr.find_all()) == 3
    assert sr.find_by_ticker("HALF", "NSE").get_screening_result("q")["passed"] is False

    events = bus.get_event_history()
    assert [type(e) for e in events] == [ScreeningCompleted, StockScored]
    assert events[0].stocks_matched == ["GOOD"] and events[0].total_evaluated == 3
    assert events[1].ticker == "GOOD" and events[1].confidence == 1.0


def test_screening_result_empty_universe():
    result = ScreeningService(StockRepositoryMemory(), MarketDataRepositoryMemory(), EventBus()).run_screen(
        Screen("q", "d", [Criterion("PE", "<", Decimal("1"))])
    )
    assert result.total_evaluated == 0 and result.match_percentage == 0


def test_event_bus_isolates_failing_handler_and_global_reset():
    bus, seen = EventBus(), []

    def bad(_e):
        raise RuntimeError("boom")

    bus.subscribe(ScreeningCompleted, bad)
    bus.subscribe(ScreeningCompleted, seen.append)
    bus.publish(ScreeningCompleted("s", [], 0))
    assert len(seen) == 1 and bus.get_subscriber_count(ScreeningCompleted) == 2
    assert get_event_bus() is get_event_bus()
    first = get_event_bus()
    reset_event_bus()
    assert get_event_bus() is not first
