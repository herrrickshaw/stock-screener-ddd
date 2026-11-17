"""Unit tests for ScreeningService scoring and event publication."""
from datetime import datetime, timedelta
from decimal import Decimal

import pytest

from src.market_data.domain.models import OHLC, MarketData, Price, Ticker
from src.market_data.domain.repositories import MarketDataRepositoryMemory
from src.shared.domain.events import ScreeningCompleted, StockScored
from src.shared.infrastructure.event_bus import EventBus
from src.stock_analysis.application.screening_service import ScreeningResult, ScreeningService
from src.stock_analysis.domain.models import Criterion, Screen
from src.stock_analysis.domain.repositories import StockRepositoryMemory
from src.stock_analysis.infrastructure.market_data_acl import MarketDataACL

D = Decimal


def md(symbol, metrics, exchange="NSE", date=None):
    p = Price(D("100"))
    m = MarketData(Ticker(symbol, exchange), date or datetime.now() - timedelta(hours=1),
                   OHLC(p, p, p, p, 1000))
    for k, v in metrics.items():
        m.add_metric(k, D(v))
    return m


@pytest.fixture
def env():
    mrepo, srepo, bus = MarketDataRepositoryMemory(), StockRepositoryMemory(), EventBus()
    return mrepo, srepo, bus, ScreeningService(srepo, mrepo, bus)


SCREEN = Screen("Quality", "d", [Criterion("PE", "<", D("20")),
                                 Criterion("DebtToEquity", "<", D("1"))])


def test_partial_score_counts_only_criteria_actually_met(env):
    mrepo, _, _, svc = env
    mrepo.save(md("AAA", {"PE": "15", "DebtToEquity": "2"}))     # 1 of 2
    score = svc.run_screen(SCREEN).stock_scores[0]
    assert (score.criteria_met, score.score) == (1, 50.0)


def test_missing_metric_never_counts_as_a_met_criterion(env):
    # matches_screen() treats a missing metric as a failure; the partial score
    # must agree, not read the missing value as 0 and pass "DebtToEquity < 1".
    mrepo, _, _, svc = env
    mrepo.save(md("AAA", {"PE": "30"}))                          # PE fails, D/E missing
    score = svc.run_screen(SCREEN).stock_scores[0]
    assert score.criteria_met == 0
    assert score.score == 0.0


def test_stock_that_failed_the_screen_never_gets_a_full_score_event(env):
    mrepo, _, bus, svc = env
    mrepo.save(md("AAA", {}))                                    # every metric missing
    result = svc.run_screen(Screen("Lows", "d", [Criterion("PE", "<", D("20"))]))
    assert result.matched_stocks == []
    assert [e for e in bus.get_event_history() if isinstance(e, StockScored)] == []


def test_matched_stock_gets_full_score_and_events(env):
    mrepo, srepo, bus, svc = env
    mrepo.save(md("AAA", {"PE": "15", "DebtToEquity": "0.5"}))
    result = svc.run_screen(SCREEN)
    assert [s.ticker for s in result.matched_stocks] == ["AAA"]
    assert result.stock_scores[0].score == 100.0
    kinds = [type(e) for e in bus.get_event_history()]
    assert kinds == [ScreeningCompleted, StockScored]
    assert srepo.find_by_ticker("AAA", "NSE").get_screening_result("Quality")["passed"] is True


def test_empty_universe(env):
    _, _, bus, svc = env
    result = svc.run_screen(SCREEN)
    assert result.total_evaluated == 0 and result.match_percentage == 0
    assert bus.get_event_history()[0].stocks_matched == []


def test_match_percentage():
    r = ScreeningResult(SCREEN, matched_stocks=[object()], stock_scores=[], total_evaluated=4)
    assert r.match_percentage == 25.0


def test_acl_freshness_follows_the_data_date_not_the_fetch_time():
    # A bar from 400 days ago that was fetched just now is not "current".
    old = md("AAA", {"PE": "10"}, date=datetime.now() - timedelta(days=400))
    stock = MarketDataACL.stock_from_market_data(old)
    assert not stock.is_fresh(30)
