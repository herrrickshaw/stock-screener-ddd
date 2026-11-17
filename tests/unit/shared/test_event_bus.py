"""Unit tests for the in-process EventBus."""
from src.shared.domain.events import ScreeningCompleted
from src.shared.infrastructure.event_bus import EventBus, get_event_bus, reset_event_bus


def ev():
    return ScreeningCompleted(screen_name="s", stocks_matched=[], total_evaluated=0)


def test_handlers_receive_event_and_history_records_it():
    bus, seen = EventBus(), []

    def h(e):
        seen.append(e)
    bus.subscribe(ScreeningCompleted, h)
    e = ev()
    bus.publish(e)
    assert seen == [e] and bus.get_event_history() == [e]
    assert bus.get_subscriber_count(ScreeningCompleted) == 1


def test_failing_handler_does_not_stop_others():
    bus, seen = EventBus(), []

    def bad(e):
        raise RuntimeError("x")

    def good(e):
        seen.append(e)
    bus.subscribe(ScreeningCompleted, bad)
    bus.subscribe(ScreeningCompleted, good)
    bus.publish(ev())
    assert len(seen) == 1


def test_publish_without_subscribers_still_records_history():
    bus = EventBus()
    bus.publish(ev())
    assert len(bus.get_event_history()) == 1
    bus.clear_history()
    assert bus.get_event_history() == []


def test_history_copy_is_defensive():
    bus = EventBus()
    bus.publish(ev())
    bus.get_event_history().clear()
    assert len(bus.get_event_history()) == 1


def test_global_bus_singleton_and_reset():
    reset_event_bus()
    a = get_event_bus()
    assert get_event_bus() is a
    reset_event_bus()
    assert get_event_bus() is not a


def test_events_get_unique_ids():
    assert ev().event_id != ev().event_id
