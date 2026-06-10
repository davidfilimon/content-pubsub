from __future__ import annotations

import hashlib
from collections import Counter, defaultdict
from typing import Dict, Iterable, List

from .models import Subscription


def stable_hash(text: str) -> int:
    return int(hashlib.sha256(text.encode("utf-8")).hexdigest(), 16)


class BalancedRendezvousRouter:
    def __init__(self, broker_ids: Iterable[str], candidate_count: int = 2) -> None:
        self.broker_ids = list(broker_ids)
        self.candidate_count = max(1, min(candidate_count, len(self.broker_ids)))
        self.global_load: Counter[str] = Counter()
        self.subscriber_load: Dict[str, Counter[str]] = defaultdict(Counter)

    def _ranked_candidates(self, subscription: Subscription) -> List[str]:
        key = subscription.routing_key()
        scored = []
        for broker_id in self.broker_ids:
            score = stable_hash(f"{key}|{broker_id}")
            scored.append((score, broker_id))
        scored.sort(reverse=True)
        return [broker_id for _, broker_id in scored[: self.candidate_count]]

    def choose_target(self, subscription: Subscription) -> str:
        candidates = self._ranked_candidates(subscription)
        subscriber_id = subscription.subscriber_id
        # Minimize per-subscriber concentration first, then global load, then stable id.
        target = min(
            candidates,
            key=lambda broker_id: (
                self.subscriber_load[subscriber_id][broker_id],
                self.global_load[broker_id],
                broker_id,
            ),
        )
        self.global_load[target] += 1
        self.subscriber_load[subscriber_id][target] += 1
        return target

    def load_snapshot(self) -> Dict[str, int]:
        return {broker_id: self.global_load[broker_id] for broker_id in self.broker_ids}
