from __future__ import annotations

from .encrypted_filter import EncryptedBrokerMatcher, EncryptedEqualitySubscription, HMACTokenizer
from .models import Publication


def main() -> None:
    tokenizer = HMACTokenizer(secret=b"project-demo-secret")
    broker = EncryptedBrokerMatcher()

    # Subscriber knows the desired content, broker stores only the HMAC token.
    sub_token = tokenizer.token("company", "Tesla")
    broker.add_subscription(
        EncryptedEqualitySubscription(
            subscription_id="secure-sub-1",
            subscriber_id="subscriber-1",
            token=sub_token,
        )
    )

    publication = Publication(
        publication_id=1,
        created_ns=0,
        company="Tesla",
        city="Bucuresti",
        value=520.0,
        category="auto",
        source="publisher-a",
    )
    tokens = tokenizer.publication_tokens(publication, fields=["company", "city", "category"])
    matches = broker.match(tokens)

    print("Broker-visible publication tokens:")
    print(tokens)
    print("Broker-visible subscription token:")
    print(sub_token)
    print("Matches without raw content access:")
    print([m.subscription_id for m in matches])


if __name__ == "__main__":
    main()
