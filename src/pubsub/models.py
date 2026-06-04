from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List
import random
import time
import uuid

from .theme_generator import COMPANIES, DATES

SOURCES = ["publisher-a", "publisher-b"]


@dataclass(frozen=True)
class Publication:
    publication_id: int
    created_ns: int
    company: str
    value: float
    drop: float
    variation: float
    date: str
    source: str

    @staticmethod
    def random(publication_id: int, source: str | None = None) -> "Publication":
        return Publication(
            publication_id=publication_id,
            created_ns=time.perf_counter_ns(),
            company=random.choice(COMPANIES),
            value=round(random.uniform(10.0, 200.0), 1),
            drop=round(random.uniform(0.0, 50.0), 1),
            variation=round(random.uniform(0.0, 5.0), 2),
            date=random.choice(DATES),
            source=source or random.choice(SOURCES),
        )

    def as_dict(self) -> Dict[str, Any]:
        return {
            "publication_id": self.publication_id,
            "created_ns": self.created_ns,
            "company": self.company,
            "value": self.value,
            "drop": self.drop,
            "variation": self.variation,
            "date": self.date,
            "source": self.source,
        }

    def as_theme_text(self) -> str:
        return (
            f'{{(company,"{self.company}");'
            f"(value,{self.value:.1f});"
            f"(drop,{self.drop:.1f});"
            f"(variation,{self.variation:.2f});"
            f"(date,{self.date})}}"
        )


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
        equality_ratio = max(0.0, min(1.0, equality_ratio))
        company = random.choice(COMPANIES)
        if random.random() < equality_ratio:
            company_condition = Condition("company", "=", company)
        else:
            company_condition = Condition("company", "!=", company)

        conditions = [company_condition]

        if not simple:
            if random.random() < 0.5:
                conditions.append(Condition("value", random.choice([">=", "<="]), round(random.uniform(10.0, 200.0), 1)))
            if random.random() < 0.5:
                conditions.append(Condition("drop", random.choice([">=", "<="]), round(random.uniform(0.0, 50.0), 1)))
            if random.random() < 0.35:
                conditions.append(Condition("variation", random.choice([">=", "<="]), round(random.uniform(0.0, 5.0), 2)))
            if random.random() < 0.35:
                conditions.append(Condition("date", random.choice(["=", "!="]), random.choice(DATES)))

        return Subscription(
            subscription_id=f"{subscriber_id}-sub-{index}-{uuid.uuid4().hex[:8]}",
            subscriber_id=subscriber_id,
            conditions=conditions,
        )

    def matches(self, publication: Publication) -> bool:
        return all(condition.matches(publication) for condition in self.conditions)

    def primary_condition(self) -> Condition:
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
