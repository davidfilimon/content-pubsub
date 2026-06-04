from __future__ import annotations

import random
from pprint import pprint

from .models import Subscription
from .overlay import BrokerOverlay
from .publisher import PublisherNode
from .subscriber import SubscriberNode


def run_demo() -> None:
    random.seed(42)
    overlay = BrokerOverlay(["broker-1", "broker-2", "broker-3"])

    subscribers = [SubscriberNode(f"subscriber-{i}") for i in range(1, 4)]
    for subscriber in subscribers:
        overlay.add_subscriber(subscriber)

    print("=== Registering random content-based subscriptions ===")
    for subscriber in subscribers:
        for index in range(5):
            entry = random.choice(overlay.broker_ids)
            subscription = Subscription.random(subscriber.subscriber_id, index, equality_ratio=0.65, simple=False)
            result = overlay.register_subscription(entry, subscription)
            print(
                f"{subscription.subscription_id}: {subscription.as_text()} | "
                f"entry={result.entry_broker} -> target={result.target_broker}, "
                f"backup={result.backup_broker}, path={result.path}"
            )

    print("\nBroker loads after registration:")
    pprint(overlay.broker_loads())

    publishers = [PublisherNode("publisher-a"), PublisherNode("publisher-b")]

    print("\n=== Publishing binary protobuf-wire messages ===")
    for _ in range(10):
        publisher = random.choice(publishers)
        entry = random.choice(overlay.broker_ids)
        payload = publisher.generate_binary_publication()
        result = overlay.publish_binary(entry, payload)
        print(
            f"publication={result.publication_id} entry={result.entry_broker} "
            f"visited={result.visited_brokers} delivered={result.delivered_notifications}"
        )

    print("\nDeliveries by subscriber:")
    pprint(overlay.subscriber_delivery_counts())

    print("\n=== Failure demo: broker-2 is stopped, replicas are used ===")
    overlay.fail_broker("broker-2")
    for _ in range(5):
        publisher = random.choice(publishers)
        entry = random.choice(overlay.broker_ids)
        result = overlay.publish_binary(entry, publisher.generate_binary_publication())
        print(
            f"publication={result.publication_id} entry={result.entry_broker} "
            f"visited={result.visited_brokers} delivered={result.delivered_notifications} "
            f"replica_matches={result.matched_on_replicas}"
        )

    print("\nFinal deliveries by subscriber:")
    pprint(overlay.subscriber_delivery_counts())


if __name__ == "__main__":
    run_demo()
