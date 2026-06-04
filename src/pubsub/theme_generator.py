"""
Pub-Sub Data Generator
Generates balanced sets of publications and subscriptions.
"""

import math
import random
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List, Optional, Tuple

# ─── Predefined values ────────────────────────────────────────────────────────

COMPANIES = [
    "Google",
    "Apple",
    "Microsoft",
    "Amazon",
    "Meta",
    "Tesla",
    "Netflix",
    "Nvidia",
    "Intel",
    "IBM",
    "Oracle",
    "Salesforce",
    "Adobe",
    "Uber",
    "Airbnb",
]

DATES = [
    "1.01.2022",
    "2.02.2022",
    "3.03.2022",
    "4.04.2022",
    "5.05.2022",
    "6.06.2022",
    "7.07.2022",
    "8.08.2022",
    "9.09.2022",
    "10.10.2022",
    "11.11.2022",
    "12.12.2022",
    "15.01.2023",
    "20.03.2023",
    "25.06.2023",
    "30.09.2023",
]

OPERATORS = ["=", "!=", "<", "<=", ">", ">="]
EQUALITY_OP = "="


# ─── Data structures ──────────────────────────────────────────────────────────


@dataclass
class Publication:
    company: str
    value: float
    drop: float
    variation: float
    date: str

    def __str__(self):
        return (
            f'{{(company,"{self.company}");'
            f"(value,{self.value:.1f});"
            f"(drop,{self.drop:.1f});"
            f"(variation,{self.variation:.2f});"
            f"(date,{self.date})}}"
        )


@dataclass
class SubscriptionField:
    name: str
    operator: str
    value: str

    def __str__(self):
        return f"({self.name},{self.operator},{self.value})"


@dataclass
class Subscription:
    fields: List[SubscriptionField] = field(default_factory=list)

    def __str__(self):
        if not self.fields:
            return "{}"
        return "{" + ";".join(str(f) for f in self.fields) + "}"


# ─── Config ───────────────────────────────────────────────────────────────────


@dataclass
class GeneratorConfig:
    num_publications: int = 1000
    num_subscriptions: int = 1000

    # Field frequencies in subscriptions (0.0 - 1.0)
    field_frequencies: dict = field(
        default_factory=lambda: {
            "company": 0.3,
            "value": 0.3,
            "drop": 0.5,
            "variation": 0,
            "date": 0,
        }
    )

    # Minimum frequency of the "=" operator for configurable fields.
    # Key = field name, value = minimum fraction of subscriptions containing the field
    # that must use the equality operator.
    equality_frequencies: dict = field(
        default_factory=lambda: {
            "company": 0.7,  # 70% of subscriptions that include "company" will use "="
        }
    )

    # Value ranges for numeric fields
    value_range: Tuple[float, float] = (10.0, 200.0)
    drop_range: Tuple[float, float] = (0.0, 50.0)
    variation_range: Tuple[float, float] = (0.0, 5.0)

    # Number of threads (1 = no parallelism)
    num_threads: int = 4


# ─── Generator ────────────────────────────────────────────────────────────────


class PubSubGenerator:
    def __init__(self, config: GeneratorConfig):
        self.config = config
        self._lock = threading.Lock()

    # ── Publications ──────────────────────────────────────────────────────────

    def _generate_publication(self) -> Publication:
        return Publication(
            company=random.choice(COMPANIES),
            value=round(random.uniform(*self.config.value_range), 1),
            drop=round(random.uniform(*self.config.drop_range), 1),
            variation=round(random.uniform(*self.config.variation_range), 2),
            date=random.choice(DATES),
        )

    def _generate_publications_chunk(self, count: int, result: list, start_idx: int):
        chunk = [self._generate_publication() for _ in range(count)]
        with self._lock:
            for i, pub in enumerate(chunk):
                result[start_idx + i] = pub

    def generate_publications(self) -> List[Publication]:
        n = self.config.num_publications
        result: List[Optional[Publication]] = [None] * n
        self._parallel_run(n, result, self._generate_publications_chunk)
        return result  # type: ignore[return-value]

    # ── Subscriptions ─────────────────────────────────────────────────────────

    def _build_subscription_masks(self, total: int) -> dict:
        """
        Computes, for each field, EXACTLY how many subscriptions will contain it.
        We use pre-assigned index permutations (not per-subscription random calls)
        to guarantee precise frequency matching.
        """
        masks = {}
        for field_name, freq in self.config.field_frequencies.items():
            count = math.ceil(freq * total)
            count = min(count, total)
            masks[field_name] = count
        return masks

    def _build_equality_masks(self, field_masks: dict, total: int) -> dict:
        """
        For fields with a configured equality frequency, computes how many
        subscriptions (among those that include the field) must use "=".
        """
        eq_masks = {}
        for field_name, eq_freq in self.config.equality_frequencies.items():
            if field_name not in field_masks:
                continue
            field_count = field_masks[field_name]
            eq_count = math.ceil(eq_freq * field_count)
            eq_masks[field_name] = min(eq_count, field_count)
        return eq_masks

    def _assign_slots(self, total: int, field_masks: dict, eq_masks: dict):
        """
        Returns, for each subscription index, the set of fields present and
        which of those fields use "=".

        Each field's index set is independently shuffled so the distribution
        is uniform while exactly matching the required frequency.
        """
        indices = list(range(total))

        # Fields present per subscription: slot_fields[i] = set of field names
        slot_fields = [set() for _ in range(total)]
        # Fields using "=" per subscription: slot_eq[i] = set of field names
        slot_eq = [set() for _ in range(total)]

        for field_name, count in field_masks.items():
            perm = list(range(total))
            random.shuffle(perm)
            chosen = set(perm[:count])

            eq_count = eq_masks.get(field_name, 0)
            # First eq_count entries from `chosen` will use "="
            chosen_list = list(chosen)
            random.shuffle(chosen_list)
            eq_chosen = set(chosen_list[:eq_count])

            for idx in chosen:
                slot_fields[idx].add(field_name)
            for idx in eq_chosen:
                slot_eq[idx].add(field_name)

        return slot_fields, slot_eq

    def _make_subscription(
        self,
        present_fields: set,
        eq_fields: set,
    ) -> Subscription:
        sub = Subscription()

        field_order = ["company", "value", "drop", "variation", "date"]

        for fname in field_order:
            if fname not in present_fields:
                continue

            if fname == "company":
                val = random.choice(COMPANIES)
                op = (
                    EQUALITY_OP
                    if fname in eq_fields
                    else random.choice([op for op in OPERATORS if op != "="])
                )
                # company only makes sense with "=" or "!="
                if op not in ("=", "!="):
                    op = "!=" if fname not in eq_fields else "="
                sub.fields.append(SubscriptionField(fname, op, f'"{val}"'))

            elif fname == "date":
                val = random.choice(DATES)
                op = EQUALITY_OP if fname in eq_fields else random.choice(["=", "!="])
                sub.fields.append(SubscriptionField(fname, op, val))

            elif fname == "value":
                val = round(random.uniform(*self.config.value_range), 1)
                op = (
                    EQUALITY_OP
                    if fname in eq_fields
                    else random.choice([o for o in OPERATORS if o != "="])
                )
                sub.fields.append(SubscriptionField(fname, op, str(val)))

            elif fname == "drop":
                val = round(random.uniform(*self.config.drop_range), 1)
                op = (
                    EQUALITY_OP
                    if fname in eq_fields
                    else random.choice([o for o in OPERATORS if o != "="])
                )
                sub.fields.append(SubscriptionField(fname, op, str(val)))

            elif fname == "variation":
                val = round(random.uniform(*self.config.variation_range), 2)
                op = (
                    EQUALITY_OP
                    if fname in eq_fields
                    else random.choice([o for o in OPERATORS if o != "="])
                )
                sub.fields.append(SubscriptionField(fname, op, str(val)))

        return sub

    def _generate_subscriptions_chunk(
        self,
        indices: List[int],
        slot_fields: list,
        slot_eq: list,
        result: list,
    ):
        for idx in indices:
            sub = self._make_subscription(slot_fields[idx], slot_eq[idx])
            result[idx] = sub

    def generate_subscriptions(self) -> List[Subscription]:
        n = self.config.num_subscriptions
        result: List[Optional[Subscription]] = [None] * n

        field_masks = self._build_subscription_masks(n)
        eq_masks = self._build_equality_masks(field_masks, n)
        slot_fields, slot_eq = self._assign_slots(n, field_masks, eq_masks)

        num_threads = self.config.num_threads
        chunk_size = math.ceil(n / num_threads)

        threads = []
        for t in range(num_threads):
            start = t * chunk_size
            end = min(start + chunk_size, n)
            if start >= n:
                break
            indices = list(range(start, end))
            thread = threading.Thread(
                target=self._generate_subscriptions_chunk,
                args=(indices, slot_fields, slot_eq, result),
            )
            threads.append(thread)

        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        return result  # type: ignore[return-value]

    def _parallel_run(self, total: int, result: list, worker_fn):
        num_threads = self.config.num_threads
        chunk_size = math.ceil(total / num_threads)
        threads = []

        for t in range(num_threads):
            start = t * chunk_size
            end = min(start + chunk_size, total)
            if start >= total:
                break
            count = end - start
            thread = threading.Thread(
                target=worker_fn,
                args=(count, result, start),
            )
            threads.append(thread)

        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

    # ── Full generation ───────────────────────────────────────────────────────

    def generate(self):
        t0 = time.perf_counter()
        publications = self.generate_publications()
        t1 = time.perf_counter()
        subscriptions = self.generate_subscriptions()
        t2 = time.perf_counter()

        return (
            publications,
            subscriptions,
            {
                "pub_time_s": round(t1 - t0, 4),
                "sub_time_s": round(t2 - t1, 4),
                "total_time_s": round(t2 - t0, 4),
            },
        )
