from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Dict, Iterable, List, Set, Tuple

from .broker import BrokerNode
from .models import Publication, Subscription
from .protobuf_codec import deserialize_publication
from .routing import BalancedRendezvousRouter
from .subscriber import SubscriberNode


@dataclass
class RegistrationResult:
    subscription_id: str
    subscriber_id: str
    entry_broker: str
    target_broker: str
    backup_broker: str
    path: List[str]


@dataclass
class PublishResult:
    publication_id: int
    entry_broker: str
    visited_brokers: List[str]
    delivered_notifications: int
    matched_on_replicas: int


class BrokerOverlay:
    """
    Ring overlay of broker nodes.

    Subscriptions are routed to one target broker selected by the advanced router.
    A backup replica is stored on the next broker in the ring. Publications are
    injected into one broker and propagated through the overlay, so each broker
    performs only local partial matching instead of one centralized match.
    """

    def __init__(self, broker_ids: Iterable[str]) -> None:
        self.brokers: Dict[str, BrokerNode] = {broker_id: BrokerNode(broker_id) for broker_id in broker_ids}
        if len(self.brokers) < 2:
            raise ValueError("Overlay requires at least two brokers")
        self.broker_ids = list(self.brokers.keys())
        self.router = BalancedRendezvousRouter(self.broker_ids, candidate_count=min(2, len(self.broker_ids)))
        self.subscribers: Dict[str, SubscriberNode] = {}
        self.neighbors: Dict[str, List[str]] = self._build_ring(self.broker_ids)
        self.registrations: List[RegistrationResult] = []

    @staticmethod
    def _build_ring(broker_ids: List[str]) -> Dict[str, List[str]]:
        neighbors: Dict[str, List[str]] = {broker_id: [] for broker_id in broker_ids}
        n = len(broker_ids)
        for index, broker_id in enumerate(broker_ids):
            left = broker_ids[(index - 1) % n]
            right = broker_ids[(index + 1) % n]
            if left not in neighbors[broker_id]:
                neighbors[broker_id].append(left)
            if right not in neighbors[broker_id]:
                neighbors[broker_id].append(right)
        return neighbors

    def add_subscriber(self, subscriber: SubscriberNode) -> None:
        self.subscribers[subscriber.subscriber_id] = subscriber

    def shortest_path(self, start: str, end: str, include_failed: bool = True) -> List[str]:
        if start == end:
            return [start]
        visited = {start}
        queue = deque([(start, [start])])
        while queue:
            current, path = queue.popleft()
            for neighbor in self.neighbors[current]:
                if neighbor in visited:
                    continue
                if not include_failed and not self.brokers[neighbor].alive:
                    continue
                next_path = path + [neighbor]
                if neighbor == end:
                    return next_path
                visited.add(neighbor)
                queue.append((neighbor, next_path))
        return [start]

    def next_alive_broker(self, broker_id: str) -> str:
        index = self.broker_ids.index(broker_id)
        for offset in range(1, len(self.broker_ids)):
            candidate = self.broker_ids[(index + offset) % len(self.broker_ids)]
            if self.brokers[candidate].alive:
                return candidate
        raise RuntimeError("No alive broker available")

    def register_subscription(self, entry_broker: str, subscription: Subscription) -> RegistrationResult:
        if subscription.subscriber_id not in self.subscribers:
            self.add_subscriber(SubscriberNode(subscription.subscriber_id))
        target = self.router.choose_target(subscription)
        backup = self.next_alive_broker(target)
        path = self.shortest_path(entry_broker, target)

        self.brokers[target].register_subscription(subscription)
        self.brokers[backup].register_replica(subscription)

        result = RegistrationResult(
            subscription_id=subscription.subscription_id,
            subscriber_id=subscription.subscriber_id,
            entry_broker=entry_broker,
            target_broker=target,
            backup_broker=backup,
            path=path,
        )
        self.registrations.append(result)
        return result

    def fail_broker(self, broker_id: str) -> None:
        self.brokers[broker_id].alive = False

    def recover_broker(self, broker_id: str) -> None:
        self.brokers[broker_id].alive = True

    def publish_binary(self, entry_broker: str, payload: bytes) -> PublishResult:
        publication = deserialize_publication(payload)
        return self.publish(entry_broker, publication)

    def publish(self, entry_broker: str, publication: Publication) -> PublishResult:
        visited: Set[str] = set()
        delivered = 0
        replica_delivered = 0
        visited_order: List[str] = []

        if not self.brokers[entry_broker].alive:
            entry_broker = self.next_alive_broker(entry_broker)

        queue = deque([(entry_broker, [entry_broker])])
        while queue:
            broker_id, path = queue.popleft()
            if broker_id in visited:
                continue
            visited.add(broker_id)
            broker = self.brokers[broker_id]
            if not broker.alive:
                continue
            visited_order.append(broker_id)

            local_deliveries = broker.match_local(publication, self.subscribers, path, use_replicas=False)
            delivered += len(local_deliveries)

            # If any neighbor is down, this broker may contain replica subscriptions
            # that cover the failed node. Duplicate protection exists at subscriber level.
            if any(not self.brokers[n].alive for n in self.neighbors[broker_id]):
                replica_deliveries = broker.match_local(publication, self.subscribers, path, use_replicas=True)
                delivered += len(replica_deliveries)
                replica_delivered += len(replica_deliveries)

            for neighbor in self.neighbors[broker_id]:
                if neighbor not in visited:
                    queue.append((neighbor, path + [neighbor]))

        return PublishResult(
            publication_id=publication.publication_id,
            entry_broker=entry_broker,
            visited_brokers=visited_order,
            delivered_notifications=delivered,
            matched_on_replicas=replica_delivered,
        )

    def broker_loads(self) -> Dict[str, Dict[str, int | bool]]:
        return {
            broker_id: {
                "alive": broker.alive,
                "local_subscriptions": broker.local_count,
                "replica_subscriptions": broker.replica_count,
            }
            for broker_id, broker in self.brokers.items()
        }

    def subscriber_delivery_counts(self) -> Dict[str, int]:
        return {sid: subscriber.deliveries_count for sid, subscriber in self.subscribers.items()}

    def all_deliveries(self):
        for subscriber in self.subscribers.values():
            yield from subscriber.received
