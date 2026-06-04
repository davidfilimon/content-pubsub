from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Set, Tuple

from .models import Delivery


@dataclass
class SubscriberNode:
    subscriber_id: str
    received: List[Delivery] = field(default_factory=list)
    _seen: Set[Tuple[int, str]] = field(default_factory=set)

    def notify(self, delivery: Delivery) -> bool:
        # Avoid duplicate notifications caused by replication/failover paths.
        key = (delivery.publication_id, delivery.subscription_id)
        if key in self._seen:
            return False
        self._seen.add(key)
        self.received.append(delivery)
        return True

    @property
    def deliveries_count(self) -> int:
        return len(self.received)
