from __future__ import annotations

from dataclasses import dataclass

from .models import Publication
from .protobuf_codec import serialize_publication


@dataclass
class PublisherNode:
    publisher_id: str
    sequence: int = 0

    def generate_publication(self) -> Publication:
        self.sequence += 1
        numeric_id = abs(hash((self.publisher_id, self.sequence))) % (2**63)
        return Publication.random(publication_id=numeric_id, source=self.publisher_id)

    def generate_binary_publication(self) -> bytes:
        return serialize_publication(self.generate_publication())
