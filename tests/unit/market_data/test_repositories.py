"""Unit tests for the in-memory MarketData repository."""
from datetime import datetime, timedelta
from decimal import Decimal

from src.market_data.domain.models import OHLC, MarketData, Price, Ticker
from src.market_data.domain.repositories import MarketDataRepositoryMemory


def md(symbol, exchange="NSE", days_ago=1, close="100"):
    p = Price(Decimal(close))
    return MarketData(Ticker(symbol, exchange), datetime.now() - timedelta(days=days_ago),
                      OHLC(p, p, p, p, 10))


def test_save_and_find_by_ticker_and_date():
    repo = MarketDataRepositoryMemory()
    m = md("INFY")
    repo.save(m)
    assert repo.find_by_ticker_and_date(m.ticker, m.date) is m


def test_same_day_resave_replaces():
    repo = MarketDataRepositoryMemory()
    repo.save(md("INFY", close="100"))
    repo.save(md("INFY", close="101"))
    assert len(repo.find_all()) == 1


def test_find_by_ticker_newest_first_and_limited():
    repo = MarketDataRepositoryMemory()
    for d in (3, 1, 2):
        repo.save(md("INFY", days_ago=d))
    out = repo.find_by_ticker(Ticker("INFY", "NSE"), days=2)
    assert [ (datetime.now() - x.date).days for x in out] == [1, 2]


def test_delete():
    repo = MarketDataRepositoryMemory()
    m = md("INFY")
    repo.save(m)
    repo.delete(m.ticker, m.date)
    assert repo.find_all() == []


def test_same_symbol_on_two_exchanges_does_not_overwrite():
    # INFY trades on NSE and (as an ADR) on NYSE; Ticker identity includes the
    # exchange, and StockRepositoryMemory keys on (ticker, exchange) too.
    repo = MarketDataRepositoryMemory()
    nse, nyse = md("INFY", "NSE"), md("INFY", "NYSE")
    repo.save(nse)
    repo.save(nyse)
    assert len(repo.find_all()) == 2
    assert repo.find_by_ticker_and_date(Ticker("INFY", "NSE"), nse.date) is nse
    assert repo.find_by_ticker(Ticker("INFY", "NYSE")) == [nyse]
