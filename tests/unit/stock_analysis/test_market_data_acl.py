"""Tests for the Market Data -> Stock Analysis anti-corruption layer."""
from datetime import datetime, timedelta
from decimal import Decimal

import pytest

from src.market_data.domain.models import OHLC, MarketData, Price, Ticker
from src.stock_analysis.infrastructure.market_data_acl import MarketDataACL

D = Decimal


def make(metrics=None, ohlc=None, date=None):
    o = ohlc or OHLC(D("10"), D("12"), D("9"), D("11"), 500)
    return MarketData(Ticker("ABC", "BSE"), date or datetime.now() - timedelta(days=2), o, metrics)


def test_ohlc_volume_and_identity_are_mapped():
    s = MarketDataACL.stock_from_market_data(make())
    assert (s.ticker, s.exchange) == ("ABC", "BSE")
    assert s.metrics == {"Open": D("10"), "High": D("12"), "Low": D("9"), "Close": D("11"),
                         "Volume": D("500")}
    assert isinstance(s.get_metric("Volume"), Decimal)


def test_each_ohlc_field_lands_in_its_own_metric():
    s = MarketDataACL.stock_from_market_data(make(ohlc=OHLC(D("2"), D("4"), D("1"), D("3"), 7)))
    assert [s.get_metric(k) for k in ("Open", "High", "Low", "Close")] == [D(2), D(4), D(1), D(3)]


def test_price_wrapped_ohlc_values_are_unwrapped():
    o = OHLC(Price(D("2")), Price(D("4")), Price(D("1")), Price(D("3")), 7)
    s = MarketDataACL.stock_from_market_data(make(ohlc=o))
    assert [s.get_metric(k) for k in ("Open", "High", "Low", "Close")] == [D(2), D(4), D(1), D(3)]
    assert all(type(s.metrics[k]) is Decimal for k in ("Open", "High", "Low", "Close"))


def test_custom_metrics_are_copied_and_can_override_ohlc_names():
    s = MarketDataACL.stock_from_market_data(make(metrics={"PE": D("15"), "Close": D("99")}))
    assert s.pe_ratio == D("15")
    assert s.get_metric("Close") == D("99")  # derived metrics are applied after OHLC


def test_float_metric_is_coerced_to_decimal():
    s = MarketDataACL.stock_from_market_data(make(metrics={"PE": 1.5}))
    assert s.pe_ratio == D("1.5")


def test_freshness_follows_data_date():
    old = MarketDataACL.stock_from_market_data(make(date=datetime.now() - timedelta(days=100)))
    new = MarketDataACL.stock_from_market_data(make(date=datetime.now() - timedelta(days=1)))
    assert old.is_fresh() is False and new.is_fresh() is True


def test_extract_metrics_defaults_to_zero_for_all_six_keys():
    out = MarketDataACL.extract_metrics(make())
    assert out == {k: D("0") for k in ("PE", "ROE", "DebtToEquity", "MarketCap", "CurrentRatio",
                                       "QuickRatio")}


def test_extract_metrics_passes_values_and_drops_unlisted():
    vals = {"PE": D("1"), "ROE": D("2"), "DebtToEquity": D("3"), "MarketCap": D("4"),
            "CurrentRatio": D("5"), "QuickRatio": D("6"), "Other": D("7")}
    out = MarketDataACL.extract_metrics(make(metrics=vals))
    assert out == {k: v for k, v in vals.items() if k != "Other"}


@pytest.mark.parametrize("ex", ["NSE", "BSE", "NASDAQ", "NYSE", "EURONEXT", "TSE"])
def test_known_exchanges_map_to_themselves(ex):
    assert MarketDataACL.map_exchange(ex) == ex


def test_unknown_exchange_passes_through_unchanged_and_case_sensitive():
    assert MarketDataACL.map_exchange("LSE") == "LSE"
    assert MarketDataACL.map_exchange("nse") == "nse"
    assert MarketDataACL.map_exchange("") == ""
