"""Tests for the shared domain base classes."""
from datetime import datetime

import pytest

from src.shared.domain.base import (
    AggregateRoot,
    ApplicationService,
    DomainEvent,
    DomainException,
    Repository,
    ValueObject,
)


class VO(ValueObject):
    def __init__(self, a, b=0):
        self.a, self.b = a, b


class VO2(ValueObject):
    def __init__(self, a, b=0):
        self.a, self.b = a, b


class Agg(AggregateRoot):
    pass


class TestValueObject:
    def test_equal_by_attributes(self):
        assert VO(1, 2) == VO(1, 2)
        assert VO(1, 2) != VO(1, 3)

    def test_different_class_never_equal_even_with_same_attrs(self):
        assert VO(1) != VO2(1)

    def test_not_equal_to_foreign_types(self):
        assert VO(1) != {"a": 1, "b": 0}
        assert (VO(1) == None) is False  # noqa: E711

    def test_subclass_and_base_instances_are_not_equal(self):
        class Sub(VO):
            pass
        assert VO(1) != Sub(1)
        assert Sub(1) != VO(1)
        assert Sub(1) == Sub(1)

    def test_hash_is_order_insensitive_and_consistent_with_eq(self):
        a = VO(1, 2)
        assert hash(a) == hash(VO(1, 2))
        assert len({VO(1, 2), VO(1, 2), VO(1, 3)}) == 2

    def test_hash_differs_for_different_values(self):
        assert hash(VO(1, 2)) != hash(VO(1, 3))


class TestDomainEvent:
    def test_ids_unique_and_timestamp_is_datetime(self):
        a, b = DomainEvent(), DomainEvent()
        assert a.event_id != b.event_id
        assert isinstance(a.timestamp, datetime)
        assert isinstance(a.event_id, str) and len(a.event_id) == 36


class TestAggregateRoot:
    def test_fresh_aggregate(self):
        a = Agg()
        assert a.domain_events == []
        assert a.id != Agg().id
        assert isinstance(a.created_at, datetime) and a.updated_at >= a.created_at

    def test_events_are_recorded_in_order(self):
        a, e1, e2 = Agg(), DomainEvent(), DomainEvent()
        a.add_domain_event(e1)
        a.add_domain_event(e2)
        assert a.domain_events == [e1, e2]

    def test_clear_returns_events_and_empties_the_aggregate(self):
        a, e1 = Agg(), DomainEvent()
        a.add_domain_event(e1)
        out = a.clear_domain_events()
        assert out == [e1]
        assert a.domain_events == []
        assert a.clear_domain_events() == []

    def test_returned_list_is_independent_of_new_events(self):
        a = Agg()
        a.add_domain_event(DomainEvent())
        out = a.clear_domain_events()
        a.add_domain_event(DomainEvent())
        assert len(out) == 1

    def test_instances_do_not_share_event_lists(self):
        a, b = Agg(), Agg()
        a.add_domain_event(DomainEvent())
        assert b.domain_events == []


class TestAbstractBases:
    def test_repository_is_abstract(self):
        with pytest.raises(TypeError):
            Repository()

    def test_application_service_is_abstract(self):
        with pytest.raises(TypeError):
            ApplicationService()

    def test_repository_abstract_bodies_return_none_via_super(self):
        class R(Repository):
            def save(self, aggregate):
                return super().save(aggregate)

            def find_by_id(self, aggregate_id):
                return super().find_by_id(aggregate_id)

            def find_all(self):
                return super().find_all()

            def delete(self, aggregate_id):
                return super().delete(aggregate_id)

        r = R()
        assert (r.save(None), r.find_by_id("x"), r.find_all(), r.delete("x")) == (None,) * 4

    def test_application_service_body_via_super_and_concrete_execute(self):
        class S(ApplicationService):
            def execute(self, *args, **kwargs):
                return super().execute(*args, **kwargs)

        class S2(ApplicationService):
            def execute(self, *args, **kwargs):
                return (args, kwargs)

        assert S().execute(1, k=2) is None
        assert S2().execute(1, k=2) == ((1,), {"k": 2})

    def test_domain_exception_is_an_exception(self):
        with pytest.raises(DomainException, match="boom"):
            raise DomainException("boom")
        assert issubclass(DomainException, Exception)
