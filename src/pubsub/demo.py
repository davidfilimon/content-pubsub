from __future__ import annotations

import random
from pprint import pprint

from .overlay import BrokerOverlay
from .publisher import PublisherNode
from .protobuf_codec import serialize_publication
from .subscriber import SubscriberNode
from .theme_adapter import generate_theme_subscriptions


def run_demo() -> None:
    random.seed(42)
    overlay = BrokerOverlay(["broker-1", "broker-2", "broker-3"])

    subscribers = [SubscriberNode(f"subscriber-{i}") for i in range(1, 4)]
    for subscriber in subscribers:
        overlay.add_subscriber(subscriber)

    print("=== Registering generated content-based subscriptions from theme generator ===")
    generated_subscriptions = generate_theme_subscriptions(
        count=15,
        subscriber_ids=[subscriber.subscriber_id for subscriber in subscribers],
        equality_ratio=0.65,
        num_threads=1,
    )
    for subscription in generated_subscriptions:
        entry = random.choice(overlay.broker_ids)
        result = overlay.register_subscription(entry, subscription)
        print(
            f"{subscription.subscription_id}: {subscription.as_text()} | "
            f"entry={result.entry_broker} -> target={result.target_broker}, "
            f"backup={result.backup_broker}, path={result.path}"
        )

    print("\nBroker loads after registration:")
    pprint(overlay.broker_loads())

    publishers = [PublisherNode("publisher-a"), PublisherNode("publisher-b")]

    print("\n=== Publishing binary protobuf-wire messages generated from theme generator ===")
    for _ in range(10):
        publisher = random.choice(publishers)
        entry = random.choice(overlay.broker_ids)
        publication = publisher.generate_publication()
        payload = serialize_publication(publication)
        result = overlay.publish_binary(entry, payload)
        print(
            f"publication={publication.as_theme_text()} source={publication.source} "
            f"entry={result.entry_broker} visited={result.visited_brokers} "
            f"delivered={result.delivered_notifications}"
        )

    print("\nDeliveries by subscriber:")
    pprint(overlay.subscriber_delivery_counts())

    print("\n=== Failure demo: broker-2 is stopped, replicas are used ===")
    overlay.fail_broker("broker-2")
    for _ in range(5):
        publisher = random.choice(publishers)
        entry = random.choice(overlay.broker_ids)
        publication = publisher.generate_publication()
        payload = serialize_publication(publication)
        result = overlay.publish_binary(entry, payload)
        print(
            f"publication={publication.as_theme_text()} source={publication.source} "
            f"entry={result.entry_broker} visited={result.visited_brokers} "
            f"delivered={result.delivered_notifications} replica_matches={result.matched_on_replicas}"
        )

    print("\nFinal deliveries by subscriber:")
    pprint(overlay.subscriber_delivery_counts())


if __name__ == "__main__":
    run_demo()
