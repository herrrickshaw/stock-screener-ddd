"""
Stock Analysis Context - Repository Interfaces
Abstracts persistence details from domain logic
"""

from abc import abstractmethod
from typing import List, Optional

from src.shared.domain.base import Repository
from .models import Stock


class StockRepository(Repository):
    """
    Repository for Stock aggregates
    This is an interface - implementations handle persistence details
    """

    @abstractmethod
    def save(self, stock: Stock) -> None:
        """Persist a stock aggregate"""
        pass

    @abstractmethod
    def find_by_ticker(self, ticker: str, exchange: str) -> Optional[Stock]:
        """Retrieve a stock by ticker and exchange"""
        pass

    @abstractmethod
    def find_all(self) -> List[Stock]:
        """Retrieve all stocks"""
        pass

    @abstractmethod
    def delete(self, ticker: str, exchange: str) -> None:
        """Delete a stock"""
        pass

    def find_by_id(self, aggregate_id: str):
        """Not used - use find_by_ticker instead"""
        raise NotImplementedError("Use find_by_ticker instead")


class StockRepositoryMemory(StockRepository):
    """Simple in-memory implementation for testing"""

    def __init__(self):
        self.stocks = {}  # key: (ticker, exchange) -> Stock

    def save(self, stock: Stock) -> None:
        key = (stock.ticker, stock.exchange)
        self.stocks[key] = stock

    def find_by_ticker(self, ticker: str, exchange: str) -> Optional[Stock]:
        key = (ticker, exchange)
        return self.stocks.get(key)

    def find_all(self) -> List[Stock]:
        return list(self.stocks.values())

    def delete(self, ticker: str, exchange: str) -> None:
        key = (ticker, exchange)
        if key in self.stocks:
            del self.stocks[key]
