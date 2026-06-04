from __future__ import annotations

import time
from typing import Iterable, List

from .models import Condition, Publication, Subscription
from .theme_generator import GeneratorConfig, PubSubGenerator
from .theme_generator import Publication as ThemePublication
from .theme_generator import Subscription as ThemeSubscription


def make_theme_config(
    num_publications: int = 0,
    num_subscriptions: int = 0,
    equality_ratio: float = 0.7,
    num_threads: int = 4,
) -> GeneratorConfig:
    return GeneratorConfig(
        num_publications=num_publications,
        num_subscriptions=num_subscriptions,
        field_frequencies={
            "company": 0.9,
            "value": 0.7,
            "drop": 0.5,
            "variation": 0.6,
            "date": 0.4,
        },
        equality_frequencies={
            "company": equality_ratio,
        },
        value_range=(10.0, 200.0),
        drop_range=(0.0, 50.0),
        variation_range=(0.0, 5.0),
        num_threads=num_threads,
    )


def publication_from_theme(theme_pub: ThemePublication, publication_id: int, source: str) -> Publication:
    return Publication(
        publication_id=publication_id,
        created_ns=time.perf_counter_ns(),
        company=theme_pub.company,
        value=float(theme_pub.value),
        drop=float(theme_pub.drop),
        variation=float(theme_pub.variation),
        date=theme_pub.date,
        source=source,
    )


def _parse_subscription_value(field_name: str, raw_value: str):
    value = str(raw_value).strip()
    if len(value) >= 2 and value[0] == '"' and value[-1] == '"':
        value = value[1:-1]
    if field_name in {"value", "drop", "variation"}:
        return float(value)
    return value


def subscription_from_theme(theme_sub: ThemeSubscription, subscriber_id: str, index: int) -> Subscription:
    conditions = [
        Condition(
            field=field.name,
            op=field.operator,
            value=_parse_subscription_value(field.name, field.value),
        )
        for field in theme_sub.fields
    ]

    # Rare case: all optional fields are absent. Keep it valid and very broad.
    if not conditions:
        conditions = [Condition("company", "!=", "__never_generated_company__")]

    return Subscription(
        subscription_id=f"{subscriber_id}-sub-{index}",
        subscriber_id=subscriber_id,
        conditions=conditions,
    )


def generate_theme_publications(count: int, source: str, start_sequence: int = 0) -> List[Publication]:
    config = make_theme_config(num_publications=count, num_subscriptions=0, num_threads=1)
    theme_publications = PubSubGenerator(config).generate_publications()
    publications: List[Publication] = []
    for offset, theme_pub in enumerate(theme_publications, start=1):
        sequence = start_sequence + offset
        numeric_id = abs(hash((source, sequence))) % (2**63)
        publications.append(publication_from_theme(theme_pub, numeric_id, source))
    return publications


def generate_theme_subscriptions(
    count: int,
    subscriber_ids: Iterable[str],
    equality_ratio: float,
    num_threads: int = 4,
) -> List[Subscription]:
    subscriber_ids = list(subscriber_ids)
    if not subscriber_ids:
        raise ValueError("At least one subscriber id is required")

    config = make_theme_config(
        num_publications=0,
        num_subscriptions=count,
        equality_ratio=equality_ratio,
        num_threads=num_threads,
    )
    theme_subscriptions = PubSubGenerator(config).generate_subscriptions()
    return [
        subscription_from_theme(
            theme_sub,
            subscriber_id=subscriber_ids[index % len(subscriber_ids)],
            index=index,
        )
        for index, theme_sub in enumerate(theme_subscriptions)
    ]
