"""Extra tests: StockScored events are emitted only for full matches, never partial scores."""
from datetime import datetime, timedelta
from decimal import Decimal

from src.market_data.domain.models import OHLC, MarketData, Price, Ticker
from src.market_data.domain.repositories import MarketDataRepositoryMemory
from src.shared.domain.events import ScreeningCompleted, StockScored
from src.shared.infrastructure.event_bus import EventBus
from src.stock_analysis.application.screening_service import ScreeningService
from src.stock_analysis.domain.models import Criterion, Screen
from src.stock_analysis.domain.repositories import StockRepositoryMemory

D = Decimal


def md(symbol, metrics):
    p = Price(D("10"))
    m = MarketData(Ticker(symbol, "NSE"), datetime.now() - timedelta(hours=1),
                   OHLC(p, p, p, p, 1))
    for k, v in metrics.items():
        m.add_metric(k, D(v))
    return m


def run(screen, *datas):
    mrepo, srepo, bus = MarketDataRepositoryMemory(), StockRepositoryMemory(), EventBus()
    for d in datas:
        mrepo.save(d)
    result = ScreeningService(srepo, mrepo, bus).run_screen(screen)
    return result, srepo, bus


SCREEN3 = Screen("s3", "d", [Criterion("PE", "<", D("20")), Criterion("ROE", ">", D("15")),
                             Criterion("DebtToEquity", "<", D("1"))])


def test_partial_matches_publish_no_stock_scored_event():
    two_of_three = md("TWO", {"PE": "10", "ROE": "20", "DebtToEquity": "5"})
    one_of_three = md("ONE", {"PE": "10", "ROE": "1", "DebtToEquity": "5"})
    result, _, bus = run(SCREEN3, two_of_three, one_of_three)
    scores = {s.stock_ticker: s for s in result.stock_scores}
    assert scores["TWO"].score == (2 / 3) * 100 and scores["TWO"].criteria_met == 2
    assert scores["ONE"].criteria_met == 1
    assert [e for e in bus.get_event_history() if isinstance(e, StockScored)] == []


def test_half_score_is_not_a_full_match_event():
    screen = Screen("s2", "d", [Criterion("PE", "<", D("20")), Criterion("ROE", ">", D("15"))])
    result, _, bus = run(screen, md("HALF", {"PE": "10", "ROE": "1"}))
    assert result.stock_scores[0].score == 50
    assert not any(isinstance(e, StockScored) for e in bus.get_event_history())


def test_full_match_publishes_scored_event_with_confidence_one_and_summary_event():
    ok = md("OK", {"PE": "10", "ROE": "20", "DebtToEquity": "0.5"})
    bad = md("BAD", {"PE": "50"})
    result, srepo, bus = run(SCREEN3, ok, bad)
    scored = [e for e in bus.get_event_history() if isinstance(e, StockScored)]
    assert [(e.ticker, e.score, e.confidence, e.screen_name) for e in scored] == [("OK", 100.0, 1.0, "s3")]
    done = [e for e in bus.get_event_history() if isinstance(e, ScreeningCompleted)]
    assert len(done) == 1 and done[0].stocks_matched == ["OK"] and done[0].total_evaluated == 2
    assert result.match_percentage == 50
    assert srepo.find_by_ticker("OK", "NSE").get_screening_result("s3")["passed"] is True
    assert srepo.find_by_ticker("BAD", "NSE").get_screening_result("s3")["passed"] is False
