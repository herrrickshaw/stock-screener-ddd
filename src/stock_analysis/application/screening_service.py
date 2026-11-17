"""
Stock Analysis Context - Application Service
Orchestrates domain logic and publishes events
"""

from typing import List
import logging

from src.stock_analysis.domain.models import Stock, Screen, StockScore
from src.stock_analysis.domain.repositories import StockRepository
from src.stock_analysis.infrastructure.market_data_acl import MarketDataACL
from src.shared.infrastructure.event_bus import EventBus
from src.shared.domain.events import ScreeningCompleted, StockScored
from src.market_data.domain.repositories import MarketDataRepository


logger = logging.getLogger(__name__)


class ScreeningService:
    """
    Application Service: Orchestrates stock screening operation

    Thin layer that:
    1. Loads aggregates from repositories
    2. Calls domain logic (Stock.matches_screen)
    3. Saves results
    4. Publishes events
    """

    def __init__(
        self,
        stock_repo: StockRepository,
        market_data_repo: MarketDataRepository,
        event_bus: EventBus
    ):
        self.stock_repo = stock_repo
        self.market_data_repo = market_data_repo
        self.event_bus = event_bus
        self.acl = MarketDataACL()

    def load_stocks_from_market_data(self) -> List[Stock]:
        """
        Load all stocks from market data and convert to domain objects
        Uses ACL to translate formats
        """
        market_data_list = self.market_data_repo.find_all()
        stocks = []

        for market_data in market_data_list:
            # ACL translates external format → domain model
            stock = self.acl.stock_from_market_data(market_data)
            stocks.append(stock)

        logger.info(f"Loaded {len(stocks)} stocks from market data")
        return stocks

    def run_screen(self, screen: Screen) -> 'ScreeningResult':
        """
        High-level operation: Run screening

        Steps:
        1. Get all stocks (load from market data if needed)
        2. Evaluate each stock (DOMAIN LOGIC in Stock.matches_screen)
        3. Record results
        4. Save updated aggregates
        5. Publish event
        """
        logger.info(f"Starting screening: {screen}")

        # Step 1: Load aggregates
        stocks = self.load_stocks_from_market_data()

        # Step 2: Apply domain logic
        matched_stocks = []
        stock_scores = []

        for stock in stocks:
            passed = stock.matches_screen(screen)  # ← DOMAIN LOGIC
            stock.record_screening_result(screen, passed)

            if passed:
                matched_stocks.append(stock)
                score = StockScore(
                    stock_ticker=stock.ticker,
                    screen_name=screen.name,
                    score=100.0,
                    criteria_met=len(screen.criteria),
                    total_criteria=len(screen.criteria)
                )
                stock_scores.append(score)
            else:
                # Calculate partial score (how many criteria matched)
                criteria_met = sum(
                    1 for c in screen.criteria
                    # a missing metric is a failed criterion, as in matches_screen()
                    if c.metric_name in stock.metrics
                    and c.matches(stock.get_metric(c.metric_name))
                )
                score = StockScore(
                    stock_ticker=stock.ticker,
                    screen_name=screen.name,
                    score=(criteria_met / len(screen.criteria)) * 100,
                    criteria_met=criteria_met,
                    total_criteria=len(screen.criteria)
                )
                stock_scores.append(score)

        # Step 3: Save updated aggregates
        for stock in stocks:
            self.stock_repo.save(stock)

        # Step 4: Publish domain event
        result = ScreeningResult(
            screen=screen,
            matched_stocks=matched_stocks,
            stock_scores=stock_scores,
            total_evaluated=len(stocks)
        )

        self.event_bus.publish(ScreeningCompleted(
            screen_name=screen.name,
            stocks_matched=[s.ticker for s in matched_stocks],
            total_evaluated=len(stocks)
        ))

        # Step 5: Publish individual stock scores
        for score in stock_scores:
            if score.criteria_percentage == 100:
                self.event_bus.publish(StockScored(
                    ticker=score.stock_ticker,
                    screen_name=score.screen_name,
                    score=score.score,
                    confidence=score.confidence,
                    criteria_met=[],  # Would be populated with actual criteria
                    criteria_failed=[]
                ))

        logger.info(f"Screening complete: {len(matched_stocks)} matches out of {len(stocks)}")
        return result


class ScreeningResult:
    """
    Result of a screening operation
    """

    def __init__(self, screen: Screen, matched_stocks: List[Stock], stock_scores: List[StockScore], total_evaluated: int):
        self.screen = screen
        self.matched_stocks = matched_stocks
        self.stock_scores = stock_scores
        self.total_evaluated = total_evaluated

    @property
    def match_percentage(self) -> float:
        """What percentage of stocks matched this screen"""
        if self.total_evaluated == 0:
            return 0
        return (len(self.matched_stocks) / self.total_evaluated) * 100

    def __str__(self) -> str:
        return f"ScreeningResult({self.screen.name}: {len(self.matched_stocks)}/{self.total_evaluated})"
