"""Extra tests: MarketData repository interface and in-memory edge cases."""
from datetime import datetime, timedelta
from decimal import Decimal

import pytest

from src.market_data.domain.models import OHLC, MarketData, Price, Ticker
from src.market_data.domain.repositories import MarketDataRepository, MarketDataRepositoryMemory


def md(symbol="X", exchange="NSE", days_ago=1):
    p = Price(Decimal("5"))
    return MarketData(Ticker(symbol, exchange), datetime.now() - timedelta(days=days_ago),
                      OHLC(p.value, p.value, p.value, p.value, 1))


def test_interface_is_abstract():
    with pytest.raises(TypeError):
        MarketDataRepository()


def test_abstract_bodies_are_noops_when_called_via_super():
    class Impl(MarketDataRepository):
        def save(self, market_data):
            return super().save(market_data)

        def find_by_ticker_and_date(self, ticker, date):
            return super().find_by_ticker_and_date(ticker, date)

        def find_by_ticker(self, ticker, days=252):
            return super().find_by_ticker(ticker, days)

        def find_all(self):
            return super().find_all()

        def delete(self, ticker, date):
            return super().delete(ticker, date)

        def find_by_id(self, aggregate_id):
            return super().find_by_id(aggregate_id)

    r, t = Impl(), Ticker("X", "NSE")
    assert r.save(md()) is None
    assert r.find_by_ticker_and_date(t, datetime.now()) is None
    assert r.find_by_ticker(t) is None
    assert r.find_all() is None
    assert r.delete(t, datetime.now()) is None
    assert r.find_by_id("x") is None


def test_find_by_id_not_supported():
    with pytest.raises(NotImplementedError, match="find_by_ticker_and_date"):
        MarketDataRepositoryMemory().find_by_id("abc")


def test_missing_lookups_and_delete_are_safe():
    r = MarketDataRepositoryMemory()
    t = Ticker("X", "NSE")
    assert r.find_by_ticker_and_date(t, datetime.now()) is None
    assert r.find_by_ticker(t) == []
    assert r.find_all() == []
    r.delete(t, datetime.now())  # no KeyError


def test_find_by_ticker_and_date_matches_on_calendar_day_not_time():
    r = MarketDataRepositoryMemory()
    m = md(days_ago=2)
    r.save(m)
    other_time = m.date.replace(hour=0, minute=0, second=0, microsecond=0)
    assert r.find_by_ticker_and_date(m.ticker, other_time) is m
    assert r.find_by_ticker_and_date(m.ticker, m.date + timedelta(days=1)) is None


def test_delete_only_removes_that_day_and_ticker():
    r = MarketDataRepositoryMemory()
    a, b, c = md("A", days_ago=1), md("A", days_ago=2), md("B", days_ago=1)
    for m in (a, b, c):
        r.save(m)
    r.delete(a.ticker, a.date)
    assert set(map(id, r.find_all())) == {id(b), id(c)}


def test_find_by_ticker_default_days_and_zero_days():
    r = MarketDataRepositoryMemory()
    for i in range(1, 4):
        r.save(md(days_ago=i))
    assert len(r.find_by_ticker(Ticker("X", "NSE"))) == 3
    assert r.find_by_ticker(Ticker("X", "NSE"), days=0) == []
    assert r.find_by_ticker(Ticker("X", "NSE"), days=1)[0].date > r.find_by_ticker(
        Ticker("X", "NSE"))[-1].date
