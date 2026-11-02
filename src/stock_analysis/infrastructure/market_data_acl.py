"""
Anti-Corruption Layer: Market Data → Stock Analysis
Translates external Market Data format into Stock Analysis domain objects

This layer isolates domain logic from external system changes.
If Market Data format changes, ONLY this file changes.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Dict, Union

from src.stock_analysis.domain.models import Stock
from src.market_data.domain.models import MarketData, Price


def _raw_value(price: Union[Price, Decimal]) -> Decimal:
    """Unwrap a Price value object to its Decimal; pass plain Decimals through."""
    return price.value if isinstance(price, Price) else price


class MarketDataACL:
    """
    Anti-Corruption Layer: Converts Market Data external format
    into Stock Analysis domain objects.

    Ensures:
    ✓ Stock Analysis doesn't know about NSE/yfinance terminology
    ✓ Format changes are isolated to this layer
    ✓ Domain logic stays pure business rules
    """

    @staticmethod
    def stock_from_market_data(market_data: MarketData) -> Stock:
        """
        Transform Market Data external format into domain Stock aggregate.

        Maps external terms to domain terms:
        - market_data.ohlc.close_price → stored as metric
        - market_data.metrics → domain-ready format
        """
        # Create stock aggregate
        stock = Stock(
            ticker=market_data.ticker.symbol,
            exchange=market_data.ticker.exchange
        )

        # Add OHLC data as metrics (extract value from Price objects)
        ohlc = market_data.ohlc
        stock.add_metric("Open", _raw_value(ohlc.open_price))
        stock.add_metric("High", _raw_value(ohlc.high_price))
        stock.add_metric("Low", _raw_value(ohlc.low_price))
        stock.add_metric("Close", _raw_value(ohlc.close_price))
        stock.add_metric("Volume", Decimal(market_data.ohlc.volume))

        # Add calculated metrics
        for metric_name, value in market_data.metrics.items():
            stock.add_metric(metric_name, value)

        # Set last updated
        stock.last_updated = market_data.fetched_at

        return stock

    @staticmethod
    def extract_metrics(market_data: MarketData) -> Dict[str, Decimal]:
        """Extract and translate financial metrics"""
        return {
            "PE": market_data.metrics.get("PE", Decimal("0")),
            "ROE": market_data.metrics.get("ROE", Decimal("0")),
            "DebtToEquity": market_data.metrics.get("DebtToEquity", Decimal("0")),
            "MarketCap": market_data.metrics.get("MarketCap", Decimal("0")),
            "CurrentRatio": market_data.metrics.get("CurrentRatio", Decimal("0")),
            "QuickRatio": market_data.metrics.get("QuickRatio", Decimal("0")),
        }

    @staticmethod
    def map_exchange(external_exchange: str) -> str:
        """Normalize exchange names (if needed for different sources)"""
        mapping = {
            "NSE": "NSE",
            "BSE": "BSE",
            "NASDAQ": "NASDAQ",
            "NYSE": "NYSE",
            "EURONEXT": "EURONEXT",
            "TSE": "TSE",
        }
        return mapping.get(external_exchange, external_exchange)
