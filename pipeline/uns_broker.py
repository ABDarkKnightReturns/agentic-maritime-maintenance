"""
Unified Namespace In-Memory Broker
-----------------------------------
Simulates MQTT/Kafka without any external dependency.
Supports wildcard subscriptions using the MQTT convention:
  +  matches one level   (e.g. "Maersk/+/EngineRoom/#")
  #  matches all remaining levels (must be last segment)

All messages flow through this broker. Subscribers receive
UNSMessage objects on a threading.Queue they own.
"""
import fnmatch
import threading
from collections import defaultdict
from queue import Queue, Empty
from typing import Callable, Optional
from models.uns import UNSMessage
from loguru import logger


class UNSBroker:

    def __init__(self):
        self._lock = threading.Lock()
        # topic_pattern -> list of (subscriber_id, queue)
        self._subscriptions: dict[str, list[tuple[str, Queue]]] = defaultdict(list)
        self._message_count = 0

    # ------------------------------------------------------------------
    # Publishing
    # ------------------------------------------------------------------

    def publish(self, message: UNSMessage) -> int:
        """
        Publish a UNSMessage. Returns number of subscribers that received it.
        Converts MQTT-style wildcards: + -> single segment, # -> any suffix.
        """
        delivered = 0
        with self._lock:
            for pattern, subscribers in self._subscriptions.items():
                if self._matches(message.topic, pattern):
                    for sub_id, q in subscribers:
                        q.put_nowait(message)
                        delivered += 1
            self._message_count += 1
        return delivered

    def publish_many(self, messages: list[UNSMessage]) -> int:
        return sum(self.publish(m) for m in messages)

    # ------------------------------------------------------------------
    # Subscribing
    # ------------------------------------------------------------------

    def subscribe(self, pattern: str, subscriber_id: str) -> Queue:
        """
        Subscribe to a topic pattern. Returns a Queue that will receive
        UNSMessage objects matching the pattern.
        """
        q: Queue = Queue(maxsize=10_000)
        with self._lock:
            self._subscriptions[pattern].append((subscriber_id, q))
        logger.debug(f"[UNS] {subscriber_id} subscribed to '{pattern}'")
        return q

    def unsubscribe(self, pattern: str, subscriber_id: str):
        with self._lock:
            self._subscriptions[pattern] = [
                (sid, q) for sid, q in self._subscriptions[pattern]
                if sid != subscriber_id
            ]

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    @staticmethod
    def _matches(topic: str, pattern: str) -> bool:
        """Convert MQTT wildcards to regex and test against topic."""
        import re
        # Escape everything, then un-escape our wildcards
        regex = re.escape(pattern)
        regex = regex.replace(r"\+", "[^/]+")   # + → one segment
        regex = regex.replace(r"\#", ".*")       # # → anything
        return bool(re.fullmatch(regex, topic))

    @property
    def stats(self) -> dict:
        with self._lock:
            return {
                "total_messages": self._message_count,
                "subscription_patterns": len(self._subscriptions),
                "total_subscribers": sum(
                    len(v) for v in self._subscriptions.values()
                ),
            }


# Module-level singleton — imported by all pipeline components
broker = UNSBroker()
