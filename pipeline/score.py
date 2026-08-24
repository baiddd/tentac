"""Stage 2 — dedupe, classify, rank. The stage that decides whether this is
a useful product or a firehose. Spend your effort here.

Input:  data/raw/<week>.jsonl
Output: data/scored/<week>.jsonl
"""

from __future__ import annotations

from models import RawItem, ScoredItem


def dedupe(items: list[RawItem]) -> list[RawItem]:
    """Collapse on dedupe_key, then near-dupe titles.

    Title matching: lowercase, strip punctuation, compare with rapidfuzz
    token_set_ratio >= 92. Keep the item from the highest-tier source and
    push the rest into mirrors.
    """
    raise NotImplementedError


def prefilter(items: list[RawItem]) -> list[RawItem]:
    """Cheap cuts before spending any tokens. Target: 400+ -> ~120 items.

    Drop: no abstract, pure survey/benchmark-rehash titles, v2+ arXiv
    revisions already published in a prior issue (check data/seen.json).
    Auto-keep: tier 1 sources, anything with a CVE, HF upvotes >= 30.
    """
    raise NotImplementedError


def classify_and_score(items: list[RawItem]) -> list[ScoredItem]:
    """One batched LLM call per ~20 items. Ask for strict JSON:

        {"url": ..., "section": <SectionId>, "score": 0..1, "why": "<=20 words"}

    Prompt guidance that matters:
      - score is "would a working practitioner regret missing this", not
        "is this well written".
      - security vs safety: an exploited vulnerability or a live incident is
        security; an eval, a policy, or interpretability work is safety.
      - `why` is the editorial line the reader sees. No hedging, no "this
        paper proposes". Say what changed.

    Validate every returned section against SectionId and drop malformed rows
    rather than trusting the model's output shape.
    """
    raise NotImplementedError


def rank(items: list[ScoredItem]) -> list[ScoredItem]:
    """Blend the model score with hard signals, then cap per section.

        final = 0.55 * model_score
              + 0.25 * social      (log-normalized HF upvotes, GitHub stars)
              + 0.20 * source_tier

    Cap at 6 items per section, 8 for security during an active incident.
    A section with 0 items renders as "quiet week" — do not pad it.
    """
    raise NotImplementedError
