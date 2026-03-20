from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class RawItem:
    id: str          # "{source}:{unique_id}" — unique per source+item
    source: str      # "github", "hackernews", "reddit", etc.
    title: str
    url: str = ""
    text: str = ""
    score: float = 0.0
    date: str = ""
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "source": self.source,
            "title": self.title,
            "url": self.url,
            "text": self.text,
            "score": self.score,
            "date": self.date,
            "metadata": self.metadata,
        }
