"""Shared schema. Every stage reads and writes these types."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Literal
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

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

_ARXIV_VERSION_RE = re.compile(r"v\d+$")


def _strip_arxiv_version(arxiv_id: str) -> str:
    return _ARXIV_VERSION_RE.sub("", arxiv_id)


def _normalize_url(url: str) -> str:
    parts = urlsplit(url)
    netloc = parts.netloc[4:] if parts.netloc.startswith("www.") else parts.netloc
    query = urlencode(
        [(k, v) for k, v in parse_qsl(parts.query) if not k.startswith("utm_")]
    )
    path = parts.path.rstrip("/") or ""
    return urlunsplit((parts.scheme, netloc, path, query, ""))


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
        if doi := self.meta.get("doi"):
            return f"doi:{doi}"
        if arxiv_id := self.meta.get("arxiv_id"):
            return f"arxiv:{_strip_arxiv_version(arxiv_id)}"
        if cve_ids := self.meta.get("cve_ids"):
            return f"cve:{cve_ids[0]}"
        return f"url:{_normalize_url(str(self.url))}"


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
    summary: str = ""  # one AI-written sentence on what happened in this section this week


class Issue(BaseModel):
    """The weekly artifact. Serialized to data/YYYY-Www.json."""

    week: str  # ISO week, e.g. "2026-W34"
    starts_on: datetime
    ends_on: datetime
    generated_at: datetime
    title: str = ""  # short punchy title (a few words), distinct from headline
    headline: str  # single-sentence take on the week
    sections: list[Section]
    stats: dict = Field(default_factory=dict)  # items_seen, items_kept, per-source counts
