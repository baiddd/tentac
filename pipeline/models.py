"""Shared schema. Every stage reads and writes these types."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, HttpUrl

SectionId = Literal[
    "llm",
    "vision",
    "multimodal",
    "systems",
    "science",
    "security",
    "safety",
    "industry",
]

ItemKind = Literal["paper", "article", "release", "advisory", "incident"]


class RawItem(BaseModel):
    """What fetch.py emits. One per URL, before dedupe or scoring."""

    source_id: str
    kind: ItemKind
    title: str
    url: HttpUrl
    published_at: datetime
    summary: str = ""
    authors: list[str] = Field(default_factory=list)
    # Source-specific extras: arxiv_id, hf_upvotes, cve_ids, ecosystem, doi...
    meta: dict = Field(default_factory=dict)

    @property
    def dedupe_key(self) -> str:
        """Normalized identity. Prefer a stable ID over the URL.

        Order of preference: DOI > arXiv ID > CVE ID > normalized URL.
        The same paper shows up on arXiv, HF Daily Papers, and a lab blog;
        these must collapse into one item that keeps all three links.
        """
        raise NotImplementedError


class ScoredItem(RawItem):
    """What score.py emits."""

    section: SectionId
    score: float  # 0..1
    why: str  # one sentence, shown in the UI as the editorial line
    mirrors: list[HttpUrl] = Field(default_factory=list)  # other URLs for same item


class Section(BaseModel):
    id: SectionId
    label: str
    blurb: str
    items: list[ScoredItem]


class Issue(BaseModel):
    """The weekly artifact. Serialized to data/YYYY-Www.json."""

    week: str  # ISO week, e.g. "2026-W34"
    starts_on: datetime
    ends_on: datetime
    generated_at: datetime
    headline: str  # single-sentence take on the week
    sections: list[Section]
    stats: dict = Field(default_factory=dict)  # items_seen, items_kept, per-source counts
