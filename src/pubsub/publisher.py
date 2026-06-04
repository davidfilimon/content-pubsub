from __future__ import annotations

from dataclasses import dataclass

from .models import Publication
from .protobuf_codec import serialize_publication
from .theme_adapter import generate_theme_publications


@dataclass
class PublisherNode:
    publisher_id: str
    sequence: int = 0

    def generate_publication(self) -> Publication:
        publication = generate_theme_publications(1, source=self.publisher_id, start_sequence=self.sequence)[0]
        self.sequence += 1
        return publication

    def generate_binary_publication(self) -> bytes:
        return serialize_publication(self.generate_publication())
