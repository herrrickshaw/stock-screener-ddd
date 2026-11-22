"""Tests for the Stock repository interface and in-memory implementation."""
from decimal import Decimal

import pytest

from src.stock_analysis.domain.models import Stock
from src.stock_analysis.domain.repositories import StockRepository, StockRepositoryMemory


def test_interface_is_abstract():
    with pytest.raises(TypeError):
        StockRepository()


def test_abstract_bodies_are_noops_via_super():
    class Impl(StockRepository):
        def save(self, stock):
            return super().save(stock)

        def find_by_ticker(self, ticker, exchange):
            return super().find_by_ticker(ticker, exchange)

        def find_all(self):
            return super().find_all()

        def delete(self, ticker, exchange):
            return super().delete(ticker, exchange)

    r = Impl()
    assert r.save(None) is None
    assert r.find_by_ticker("X", "NSE") is None
    assert r.find_all() is None
    assert r.delete("X", "NSE") is None
    with pytest.raises(NotImplementedError, match="find_by_ticker"):
        r.find_by_id("x")


class TestMemoryRepo:
    def test_save_find_and_find_all(self):
        r = StockRepositoryMemory()
        a, b = Stock("A", "NSE"), Stock("B", "NSE")
        r.save(a)
        r.save(b)
        assert r.find_by_ticker("A", "NSE") is a
        assert set(map(id, r.find_all())) == {id(a), id(b)}

    def test_missing_returns_none(self):
        assert StockRepositoryMemory().find_by_ticker("A", "NSE") is None
        assert StockRepositoryMemory().find_all() == []

    def test_key_includes_exchange(self):
        r = StockRepositoryMemory()
        a, b = Stock("A", "NSE"), Stock("A", "BSE")
        r.save(a)
        r.save(b)
        assert r.find_by_ticker("A", "NSE") is a and r.find_by_ticker("A", "BSE") is b
        assert r.find_by_ticker("A", "NYSE") is None

    def test_resave_replaces(self):
        r = StockRepositoryMemory()
        r.save(Stock("A", "NSE"))
        newer = Stock("A", "NSE", {"PE": Decimal("1")})
        r.save(newer)
        assert r.find_by_ticker("A", "NSE") is newer and len(r.find_all()) == 1

    def test_delete_only_targets_given_exchange_and_missing_is_safe(self):
        r = StockRepositoryMemory()
        r.save(Stock("A", "NSE"))
        r.save(Stock("A", "BSE"))
        r.delete("A", "NSE")
        r.delete("A", "NSE")
        r.delete("Z", "NSE")
        assert r.find_by_ticker("A", "NSE") is None
        assert r.find_by_ticker("A", "BSE") is not None

    def test_find_by_id_not_supported(self):
        with pytest.raises(NotImplementedError):
            StockRepositoryMemory().find_by_id("x")
