from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List
import random
import time
import uuid


COMPANIES = ["Google", "Amazon", "Microsoft", "Tesla", "Apple", "Nvidia", "BMW", "Dacia"]
CITIES = ["Bucuresti", "Constanta", "Iasi", "Cluj", "Brasov", "Timisoara", "Sibiu"]
CATEGORIES = ["tech", "auto", "finance", "robotics", "energy", "retail"]
SOURCES = ["publisher-a", "publisher-b"]


@dataclass(frozen=True)
class Publication:
    publication_id: int
    created_ns: int
    company: str
    city: str
    value: float
    category: str
    source: str

    @staticmethod
    def random(publication_id: int, source: str | None = None) -> "Publication":
        return Publication(
            publication_id=publication_id,
            created_ns=time.perf_counter_ns(),
            company=random.choice(COMPANIES),
            city=random.choice(CITIES),
            value=round(random.uniform(0.0, 1000.0), 3),
            category=random.choice(CATEGORIES),
            source=source or random.choice(SOURCES),
        )

    def as_dict(self) -> Dict[str, Any]:
        return {
            "publication_id": self.publication_id,
            "created_ns": self.created_ns,
            "company": self.company,
            "city": self.city,
            "value": self.value,
            "category": self.category,
            "source": self.source,
        }


@dataclass(frozen=True)
class Condition:
    field: str
    op: str
    value: Any

    def matches(self, publication: Publication) -> bool:
        actual = getattr(publication, self.field)
        expected = self.value
        if self.op == "=":
            return actual == expected
        if self.op == "!=":
            return actual != expected
        if self.op == ">":
            return actual > expected
        if self.op == ">=":
            return actual >= expected
        if self.op == "<":
            return actual < expected
        if self.op == "<=":
            return actual <= expected
        raise ValueError(f"Unsupported operator: {self.op}")

    def routing_key(self) -> str:
        return f"{self.field}:{self.op}:{self.value}"


@dataclass(frozen=True)
class Subscription:
    subscription_id: str
    subscriber_id: str
    conditions: List[Condition]
    created_ns: int = field(default_factory=time.perf_counter_ns)

    @staticmethod
    def random(
        subscriber_id: str,
        index: int,
        equality_ratio: float = 1.0,
        simple: bool = True,
    ) -> "Subscription":
        """
        Generate a content-based subscription.

        For evaluation we use a controlled field, `company`, and vary how often the
        operator on that field is equality. This directly supports the 100% vs 25%
        matching-rate comparison requested in the project statement.
        """
        equality_ratio = max(0.0, min(1.0, equality_ratio))
        company = random.choice(COMPANIES)
        if random.random() < equality_ratio:
            company_condition = Condition("company", "=", company)
        else:
            company_condition = Condition("company", "!=", company)

        conditions = [company_condition]

        if not simple:
            # Optional extra filters used by the demo. Evaluation keeps subscriptions simple.
            if random.random() < 0.5:
                conditions.append(Condition("city", "=", random.choice(CITIES)))
            if random.random() < 0.5:
                op = random.choice([">=", "<="])
                conditions.append(Condition("value", op, round(random.uniform(100.0, 900.0), 3)))
            if random.random() < 0.35:
                conditions.append(Condition("category", "=", random.choice(CATEGORIES)))

        return Subscription(
            subscription_id=f"{subscriber_id}-sub-{index}-{uuid.uuid4().hex[:8]}",
            subscriber_id=subscriber_id,
            conditions=conditions,
        )

    def matches(self, publication: Publication) -> bool:
        return all(condition.matches(publication) for condition in self.conditions)

    def primary_condition(self) -> Condition:
        # Prefer equality conditions because they are more selective for routing.
        for condition in self.conditions:
            if condition.op == "=":
                return condition
        return self.conditions[0]

    def routing_key(self) -> str:
        return self.primary_condition().routing_key()

    def as_text(self) -> str:
        parts = [f"{c.field} {c.op} {c.value}" for c in self.conditions]
        return " AND ".join(parts)


@dataclass
class Delivery:
    publication_id: int
    subscriber_id: str
    subscription_id: str
    broker_id: str
    emitted_ns: int
    delivered_ns: int
    path: List[str]
    replica_delivery: bool = False

    @property
    def latency_ms(self) -> float:
        return (self.delivered_ns - self.emitted_ns) / 1_000_000.0
