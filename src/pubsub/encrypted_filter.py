from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass
from typing import Dict, Iterable, List, Set

from .models import Publication


class HMACTokenizer:
    def __init__(self, secret: bytes) -> None:
        self.secret = secret

    def token(self, field: str, value: object) -> str:
        msg = f"{field}={value}".encode("utf-8")
        return hmac.new(self.secret, msg, hashlib.sha256).hexdigest()

    def publication_tokens(
        self, publication: Publication, fields: Iterable[str]
    ) -> Set[str]:
        return {self.token(field, getattr(publication, field)) for field in fields}


@dataclass(frozen=True)
class EncryptedEqualitySubscription:
    subscription_id: str
    subscriber_id: str
    token: str

    def matches_tokens(self, publication_tokens: Set[str]) -> bool:
        return self.token in publication_tokens


class EncryptedBrokerMatcher:
    def __init__(self) -> None:
        self.subscriptions: List[EncryptedEqualitySubscription] = []

    def add_subscription(self, subscription: EncryptedEqualitySubscription) -> None:
        self.subscriptions.append(subscription)

    def match(
        self, publication_tokens: Set[str]
    ) -> List[EncryptedEqualitySubscription]:
        return [
            sub for sub in self.subscriptions if sub.matches_tokens(publication_tokens)
        ]
