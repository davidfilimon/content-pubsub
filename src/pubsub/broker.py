from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Sequence, Set, Tuple
import time

from .models import Delivery, Publication, Subscription
from .subscriber import SubscriberNode


@dataclass
class BrokerNode:
    broker_id: str
    subscriptions: List[Subscription] = field(default_factory=list)
    replica_subscriptions: List[Subscription] = field(default_factory=list)
    alive: bool = True

    def register_subscription(self, subscription: Subscription) -> None:
        self.subscriptions.append(subscription)

    def register_replica(self, subscription: Subscription) -> None:
        # Replicas are used only if the primary broker fails.
        self.replica_subscriptions.append(subscription)

    def match_local(
        self,
        publication: Publication,
        subscribers: Dict[str, SubscriberNode],
        path: Sequence[str],
        use_replicas: bool = False,
    ) -> List[Delivery]:
        source = self.replica_subscriptions if use_replicas else self.subscriptions
        deliveries: List[Delivery] = []
        now = time.perf_counter_ns

        for subscription in source:
            subscriber = subscribers.get(subscription.subscriber_id)
            if subscriber is None:
                continue
            if not subscription.matches(publication):
                continue

            delivery = Delivery(
                publication_id=publication.publication_id,
                subscriber_id=subscription.subscriber_id,
                subscription_id=subscription.subscription_id,
                broker_id=self.broker_id,
                emitted_ns=publication.created_ns,
                delivered_ns=now(),
                path=list(path),
                replica_delivery=use_replicas,
            )
            if subscriber.notify(delivery):
                deliveries.append(delivery)

        return deliveries

    @property
    def local_count(self) -> int:
        return len(self.subscriptions)

    @property
    def replica_count(self) -> int:
        return len(self.replica_subscriptions)
