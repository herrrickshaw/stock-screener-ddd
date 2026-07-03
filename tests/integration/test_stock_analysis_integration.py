"""
Integration tests: Stock Analysis context with Market Data context
Verify ACL translation and screening orchestration
"""

import pytest
from datetime import datetime
from decimal import Decimal

from src.market_data.domain.models import (
    Ticker, Price, OHLC, MarketData, MarketCalendar
)
from src.market_data.domain.repositories import MarketDataRepositoryMemory
from src.stock_analysis.domain.models import Criterion, Screen, Stock
from src.stock_analysis.domain.repositories import StockRepositoryMemory
from src.stock_analysis.infrastructure.market_data_acl import MarketDataACL
from src.stock_analysis.application.screening_service import ScreeningService
from src.shared.infrastructure.event_bus import EventBus
from src.shared.domain.events import ScreeningCompleted, StockScored


@pytest.fixture
def market_data_repo():
    return MarketDataRepositoryMemory()


@pytest.fixture
def stock_repo():
    return StockRepositoryMemory()


@pytest.fixture
def event_bus():
    return EventBus()


@pytest.fixture
def screening_service(stock_repo, market_data_repo, event_bus):
    return ScreeningService(stock_repo, market_data_repo, event_bus)


class TestACLTranslation:
    """Test Anti-Corruption Layer translates Market Data → Stock"""

    def test_stock_from_market_data_basic(self):
        """ACL translates market data aggregate to stock aggregate"""
        ticker = Ticker(symbol="INFY", exchange="NSE")
        ohlc = OHLC(
            open_price=Price(Decimal("1500.00"), "INR"),
            high_price=Price(Decimal("1550.00"), "INR"),
            low_price=Price(Decimal("1480.00"), "INR"),
            close_price=Price(Decimal("1520.00"), "INR"),
            volume=1000000
        )
        market_data = MarketData(ticker=ticker, date=datetime.now(), ohlc=ohlc)
        market_data.add_metric("PE", Decimal("25.0"))
        market_data.add_metric("ROE", Decimal("18.5"))

        acl = MarketDataACL()
        stock = acl.stock_from_market_data(market_data)

        assert stock.ticker == "INFY"
        assert stock.exchange == "NSE"
        assert stock.get_metric("Open") == Decimal("1500.00")
        assert stock.get_metric("Close") == Decimal("1520.00")
        assert stock.get_metric("PE") == Decimal("25.0")
        assert stock.get_metric("ROE") == Decimal("18.5")

    def test_stock_from_market_data_ohlc_preservation(self):
        """ACL preserves full OHLC data"""
        ticker = Ticker(symbol="TCS", exchange="NSE")
        ohlc = OHLC(
            open_price=Price(Decimal("3600.00"), "INR"),
            high_price=Price(Decimal("3650.00"), "INR"),
            low_price=Price(Decimal("3580.00"), "INR"),
            close_price=Price(Decimal("3620.00"), "INR"),
            volume=500000
        )
        market_data = MarketData(ticker=ticker, date=datetime.now(), ohlc=ohlc)

        acl = MarketDataACL()
        stock = acl.stock_from_market_data(market_data)

        assert stock.get_metric("Open") == Decimal("3600.00")
        assert stock.get_metric("High") == Decimal("3650.00")
        assert stock.get_metric("Low") == Decimal("3580.00")
        assert stock.get_metric("Close") == Decimal("3620.00")
        assert stock.get_metric("Volume") == Decimal("500000")

    def test_acl_isolates_external_format_changes(self):
        """Stock Analysis doesn't know about external market data format"""
        ticker = Ticker(symbol="HDFC", exchange="NSE")
        ohlc = OHLC(
            open_price=Price(Decimal("2500.00"), "INR"),
            high_price=Price(Decimal("2550.00"), "INR"),
            low_price=Price(Decimal("2480.00"), "INR"),
            close_price=Price(Decimal("2520.00"), "INR"),
            volume=300000
        )
        market_data = MarketData(ticker=ticker, date=datetime.now(), ohlc=ohlc)

        # Stock aggregate created by ACL has no knowledge of:
        # - Ticker value object
        # - Price value object
        # - OHLC value object
        # - MarketCalendar

        acl = MarketDataACL()
        stock = acl.stock_from_market_data(market_data)

        assert hasattr(stock, "metrics")
        assert isinstance(stock.metrics, dict)
        assert stock.ticker == "HDFC"  # Raw string, not Ticker VO


class TestScreeningService:
    """Test Application Service orchestration"""

    def test_load_stocks_from_market_data(self, screening_service, market_data_repo):
        """Service loads stocks from market data context"""
        # Setup market data
        ticker1 = Ticker(symbol="INFY", exchange="NSE")
        ohlc1 = OHLC(
            open_price=Price(Decimal("1500.00"), "INR"),
            high_price=Price(Decimal("1550.00"), "INR"),
            low_price=Price(Decimal("1480.00"), "INR"),
            close_price=Price(Decimal("1520.00"), "INR"),
            volume=1000000
        )
        market_data1 = MarketData(ticker=ticker1, date=datetime.now(), ohlc=ohlc1)
        market_data1.add_metric("PE", Decimal("25.0"))
        market_data_repo.save(market_data1)

        ticker2 = Ticker(symbol="TCS", exchange="NSE")
        ohlc2 = OHLC(
            open_price=Price(Decimal("3600.00"), "INR"),
            high_price=Price(Decimal("3650.00"), "INR"),
            low_price=Price(Decimal("3580.00"), "INR"),
            close_price=Price(Decimal("3620.00"), "INR"),
            volume=500000
        )
        market_data2 = MarketData(ticker=ticker2, date=datetime.now(), ohlc=ohlc2)
        market_data2.add_metric("PE", Decimal("30.0"))
        market_data_repo.save(market_data2)

        # Load stocks
        stocks = screening_service.load_stocks_from_market_data()

        assert len(stocks) == 2
        tickers = {s.ticker for s in stocks}
        assert "INFY" in tickers
        assert "TCS" in tickers

    def test_run_screen_all_matches(self, screening_service, market_data_repo, event_bus):
        """Service runs screening and publishes events"""
        # Setup: Two stocks with PE < 30
        ticker1 = Ticker(symbol="INFY", exchange="NSE")
        ohlc1 = OHLC(
            open_price=Price(Decimal("1500.00"), "INR"),
            high_price=Price(Decimal("1550.00"), "INR"),
            low_price=Price(Decimal("1480.00"), "INR"),
            close_price=Price(Decimal("1520.00"), "INR"),
            volume=1000000
        )
        market_data1 = MarketData(ticker=ticker1, date=datetime.now(), ohlc=ohlc1)
        market_data1.add_metric("PE", Decimal("25.0"))
        market_data_repo.save(market_data1)

        ticker2 = Ticker(symbol="TCS", exchange="NSE")
        ohlc2 = OHLC(
            open_price=Price(Decimal("3600.00"), "INR"),
            high_price=Price(Decimal("3650.00"), "INR"),
            low_price=Price(Decimal("3580.00"), "INR"),
            close_price=Price(Decimal("3620.00"), "INR"),
            volume=500000
        )
        market_data2 = MarketData(ticker=ticker2, date=datetime.now(), ohlc=ohlc2)
        market_data2.add_metric("PE", Decimal("28.0"))
        market_data_repo.save(market_data2)

        # Screen: PE < 30
        criterion = Criterion(metric_name="PE", operator="<", threshold=Decimal("30"))
        screen = Screen(
            name="Low PE",
            description="PE < 30",
            criteria=[criterion]
        )

        # Run screening
        result = screening_service.run_screen(screen)

        # Verify results
        assert result.total_evaluated == 2
        assert len(result.matched_stocks) == 2
        assert result.match_percentage == 100.0

    def test_run_screen_partial_matches(self, screening_service, market_data_repo):
        """Service correctly identifies partial matches"""
        # Setup: One stock matches, one doesn't
        ticker1 = Ticker(symbol="INFY", exchange="NSE")
        ohlc1 = OHLC(
            open_price=Price(Decimal("1500.00"), "INR"),
            high_price=Price(Decimal("1550.00"), "INR"),
            low_price=Price(Decimal("1480.00"), "INR"),
            close_price=Price(Decimal("1520.00"), "INR"),
            volume=1000000
        )
        market_data1 = MarketData(ticker=ticker1, date=datetime.now(), ohlc=ohlc1)
        market_data1.add_metric("PE", Decimal("25.0"))
        market_data_repo.save(market_data1)

        ticker2 = Ticker(symbol="TCS", exchange="NSE")
        ohlc2 = OHLC(
            open_price=Price(Decimal("3600.00"), "INR"),
            high_price=Price(Decimal("3650.00"), "INR"),
            low_price=Price(Decimal("3580.00"), "INR"),
            close_price=Price(Decimal("3620.00"), "INR"),
            volume=500000
        )
        market_data2 = MarketData(ticker=ticker2, date=datetime.now(), ohlc=ohlc2)
        market_data2.add_metric("PE", Decimal("35.0"))
        market_data_repo.save(market_data2)

        # Screen: PE < 30
        criterion = Criterion(metric_name="PE", operator="<", threshold=Decimal("30"))
        screen = Screen(
            name="Low PE",
            description="PE < 30",
            criteria=[criterion]
        )

        result = screening_service.run_screen(screen)

        assert result.total_evaluated == 2
        assert len(result.matched_stocks) == 1
        assert result.matched_stocks[0].ticker == "INFY"
        assert result.match_percentage == 50.0

    def test_run_screen_publishes_events(self, screening_service, market_data_repo, event_bus):
        """Service publishes domain events"""
        ticker = Ticker(symbol="INFY", exchange="NSE")
        ohlc = OHLC(
            open_price=Price(Decimal("1500.00"), "INR"),
            high_price=Price(Decimal("1550.00"), "INR"),
            low_price=Price(Decimal("1480.00"), "INR"),
            close_price=Price(Decimal("1520.00"), "INR"),
            volume=1000000
        )
        market_data = MarketData(ticker=ticker, date=datetime.now(), ohlc=ohlc)
        market_data.add_metric("PE", Decimal("25.0"))
        market_data_repo.save(market_data)

        criterion = Criterion(metric_name="PE", operator="<", threshold=Decimal("30"))
        screen = Screen(
            name="Low PE",
            description="PE < 30",
            criteria=[criterion]
        )

        screening_service.run_screen(screen)

        # Verify ScreeningCompleted event published
        events = event_bus.get_event_history()
        completed_events = [e for e in events if isinstance(e, ScreeningCompleted)]
        assert len(completed_events) == 1
        assert completed_events[0].screen_name == "Low PE"
        assert len(completed_events[0].stocks_matched) == 1

    def test_screening_saves_results_to_repository(
        self, screening_service, market_data_repo, stock_repo
    ):
        """Service saves screening results to stock repository"""
        ticker = Ticker(symbol="INFY", exchange="NSE")
        ohlc = OHLC(
            open_price=Price(Decimal("1500.00"), "INR"),
            high_price=Price(Decimal("1550.00"), "INR"),
            low_price=Price(Decimal("1480.00"), "INR"),
            close_price=Price(Decimal("1520.00"), "INR"),
            volume=1000000
        )
        market_data = MarketData(ticker=ticker, date=datetime.now(), ohlc=ohlc)
        market_data.add_metric("PE", Decimal("25.0"))
        market_data_repo.save(market_data)

        criterion = Criterion(metric_name="PE", operator="<", threshold=Decimal("30"))
        screen = Screen(
            name="Low PE",
            description="PE < 30",
            criteria=[criterion]
        )

        screening_service.run_screen(screen)

        # Verify stock saved to repository with screening result
        saved_stock = stock_repo.find_by_ticker("INFY", "NSE")
        assert saved_stock is not None
        screening_result = saved_stock.get_screening_result("Low PE")
        assert screening_result["passed"] is True

    def test_multiple_criteria_screening(self, screening_service, market_data_repo):
        """Service handles screens with multiple criteria"""
        ticker = Ticker(symbol="INFY", exchange="NSE")
        ohlc = OHLC(
            open_price=Price(Decimal("1500.00"), "INR"),
            high_price=Price(Decimal("1550.00"), "INR"),
            low_price=Price(Decimal("1480.00"), "INR"),
            close_price=Price(Decimal("1520.00"), "INR"),
            volume=1000000
        )
        market_data = MarketData(ticker=ticker, date=datetime.now(), ohlc=ohlc)
        market_data.add_metric("PE", Decimal("25.0"))
        market_data.add_metric("ROE", Decimal("20.0"))
        market_data_repo.save(market_data)

        # Screen: PE < 30 AND ROE > 15
        criteria = [
            Criterion(metric_name="PE", operator="<", threshold=Decimal("30")),
            Criterion(metric_name="ROE", operator=">", threshold=Decimal("15"))
        ]
        screen = Screen(
            name="Quality Growth",
            description="Low PE and High ROE",
            criteria=criteria
        )

        result = screening_service.run_screen(screen)

        assert len(result.matched_stocks) == 1
        assert result.matched_stocks[0].ticker == "INFY"


class TestContextBoundary:
    """Test boundary between Market Data and Stock Analysis contexts"""

    def test_market_data_format_changes_isolated(self, screening_service, market_data_repo):
        """Changes to Market Data format don't affect Stock Analysis logic"""
        # This test verifies the ACL isolation principle
        # If Market Data changes from OHLC to HLC (removing Open), only ACL changes

        ticker = Ticker(symbol="INFY", exchange="NSE")
        ohlc = OHLC(
            open_price=Price(Decimal("1500.00"), "INR"),
            high_price=Price(Decimal("1550.00"), "INR"),
            low_price=Price(Decimal("1480.00"), "INR"),
            close_price=Price(Decimal("1520.00"), "INR"),
            volume=1000000
        )
        market_data = MarketData(ticker=ticker, date=datetime.now(), ohlc=ohlc)
        market_data_repo.save(market_data)

        # Stock Analysis screening logic doesn't care about OHLC structure
        criterion = Criterion(metric_name="Close", operator="<", threshold=Decimal("1550"))
        screen = Screen(name="Test", description="Test", criteria=[criterion])

        result = screening_service.run_screen(screen)
        assert len(result.matched_stocks) == 1
