"""Extra tests: subscriber counts, handler ordering/isolation, global bus lifecycle."""
import logging

import pytest

import src.shared.infrastructure.event_bus as eb
from src.shared.domain.events import DataValidationFailed, ScreeningCompleted
from src.shared.infrastructure.event_bus import EventBus, get_event_bus, reset_event_bus


def sc():
    return ScreeningCompleted("s", [], 0)


@pytest.fixture(autouse=True)
def _restore_global_bus():
    saved = eb._event_bus
    yield
    eb._event_bus = saved


def test_subscriber_count_per_type():
    b = EventBus()
    assert b.get_subscriber_count(ScreeningCompleted) == 0
    b.subscribe(ScreeningCompleted, lambda e: None)
    b.subscribe(ScreeningCompleted, lambda e: None)
    b.subscribe(DataValidationFailed, lambda e: None)
    assert b.get_subscriber_count(ScreeningCompleted) == 2
    assert b.get_subscriber_count(DataValidationFailed) == 1


def test_get_subscriber_count_does_not_create_entries():
    b = EventBus()
    b.get_subscriber_count(ScreeningCompleted)
    assert ScreeningCompleted not in b.subscribers


def test_handlers_run_in_subscription_order_only_for_their_type():
    b, calls = EventBus(), []
    b.subscribe(ScreeningCompleted, lambda e: calls.append("a"))
    b.subscribe(ScreeningCompleted, lambda e: calls.append("b"))
    b.subscribe(DataValidationFailed, lambda e: calls.append("other"))
    b.publish(sc())
    assert calls == ["a", "b"]


def test_subclass_events_are_not_delivered_to_base_type_subscribers():
    # dispatch is on exact type(event)
    class Sub(ScreeningCompleted):
        pass

    b, calls = EventBus(), []
    b.subscribe(ScreeningCompleted, lambda e: calls.append(e))
    b.publish(Sub("s", [], 0))
    assert calls == []


def test_failure_is_logged_with_handler_name_and_later_handlers_still_run(caplog):
    b, calls = EventBus(), []

    def explode(e):
        raise RuntimeError("kaboom")

    b.subscribe(ScreeningCompleted, explode)
    b.subscribe(ScreeningCompleted, lambda e: calls.append(1))
    with caplog.at_level(logging.ERROR, logger=eb.logger.name):
        b.publish(sc())
    assert calls == [1]
    assert any("explode" in r.getMessage() and "kaboom" in r.getMessage() for r in caplog.records)


def test_no_subscriber_warning_logged(caplog):
    b = EventBus()
    with caplog.at_level(logging.WARNING, logger=eb.logger.name):
        b.publish(sc())
    assert any("No subscribers" in r.getMessage() for r in caplog.records)


def test_clear_history():
    b = EventBus()
    b.publish(sc())
    b.clear_history()
    assert b.get_event_history() == []


def test_get_event_bus_lazily_creates_and_reuses():
    eb._event_bus = None
    first = get_event_bus()
    assert isinstance(first, EventBus) and get_event_bus() is first


def test_reset_replaces_instance_and_drops_subscribers():
    first = get_event_bus()
    first.subscribe(ScreeningCompleted, lambda e: None)
    reset_event_bus()
    second = get_event_bus()
    assert second is not first and second.get_subscriber_count(ScreeningCompleted) == 0
