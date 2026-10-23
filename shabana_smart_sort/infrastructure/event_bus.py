"""Typed event bus for decoupled pub/sub events throughout the system."""
from typing import Callable, Dict, List, Type, Any
import logging
import threading

logger = logging.getLogger("ShabanaSmartSort.EventBus")


class Event:
    """Base class for all system events."""
    pass


class ScanProgressEvent(Event):
    def __init__(self, current_file: str, scanned_count: int, total_estimate: int = 0):
        self.current_file = current_file
        self.scanned_count = scanned_count
        self.total_estimate = total_estimate


class ScanCompletedEvent(Event):
    def __init__(self, total_files: int, total_size_bytes: int, duration_sec: float):
        self.total_files = total_files
        self.total_size_bytes = total_size_bytes
        self.duration_sec = duration_sec


class SortProgressEvent(Event):
    def __init__(self, current: int, total: int, current_filename: str, status: str):
        self.current = current
        self.total = total
        self.current_filename = current_filename
        self.status = status


class SortCompletedEvent(Event):
    def __init__(self, job_id: str, succeeded: int, failed: int, skipped: int):
        self.job_id = job_id
        self.succeeded = succeeded
        self.failed = failed
        self.skipped = skipped


class UndoProgressEvent(Event):
    def __init__(self, current: int, total: int, filename: str):
        self.current = current
        self.total = total
        self.filename = filename


class RulesChangedEvent(Event):
    """Fired whenever rules are added, updated, reordered, deleted, or toggled."""
    def __init__(self, action: str = "updated", rule_id: str = ""):
        self.action = action
        self.rule_id = rule_id


class EventBus:
    """Thread-safe event pub/sub dispatcher."""

    def __init__(self):
        self._subscribers: Dict[Type[Event], List[Callable[[Any], None]]] = {}
        self._lock = threading.Lock()

    def subscribe(self, event_type: Type[Event], handler: Callable[[Any], None]) -> None:
        with self._lock:
            if event_type not in self._subscribers:
                self._subscribers[event_type] = []
            self._subscribers[event_type].append(handler)

    def unsubscribe(self, event_type: Type[Event], handler: Callable[[Any], None]) -> None:
        with self._lock:
            if event_type in self._subscribers:
                try:
                    self._subscribers[event_type].remove(handler)
                except ValueError:
                    pass

    def publish(self, event: Event) -> None:
        handlers = []
        with self._lock:
            handlers = list(self._subscribers.get(type(event), []))
        for handler in handlers:
            try:
                handler(event)
            except Exception as e:
                logger.error(f"Error handling event {type(event).__name__}: {e}", exc_info=True)


# Global instance
event_bus = EventBus()
