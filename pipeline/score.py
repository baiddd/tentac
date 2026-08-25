"""Stage 2 — dedupe, classify, rank. The stage that decides whether this is
a useful product or a firehose. Spend your effort here.

Input:  data/raw/<week>.jsonl
Output: data/scored/<week>.jsonl
"""

from __future__ import annotations

from models import RawItem, ScoredItem


SOURCE_TIERS: dict[str, int] = {}


def _tier(source_id: str) -> int:
    return SOURCE_TIERS.get(source_id, 3)


def _load_seen() -> set[str]:
    import json
    import os

    if not os.path.exists("data/seen.json"):
        return set()
    with open("data/seen.json") as f:
        return set(json.load(f))


def dedupe(items: list[RawItem]) -> list[RawItem]:
    """Collapse on dedupe_key, then near-dupe titles.

    Title matching: lowercase, strip punctuation, compare with rapidfuzz
    token_set_ratio >= 92. Keep the item from the highest-tier source and
    push the rest into mirrors.
    """
    import re

    from rapidfuzz import fuzz

    groups: list[list[RawItem]] = []
    key_to_group: dict[str, int] = {}

    for item in items:
        key = item.dedupe_key
        if key in key_to_group:
            groups[key_to_group[key]].append(item)
            continue

        normalized_title = re.sub(r"[^\w\s]", "", item.title.lower())
        matched_group = None
        for idx, group in enumerate(groups):
            for member in group:
                member_title = re.sub(r"[^\w\s]", "", member.title.lower())
                if fuzz.token_set_ratio(normalized_title, member_title) >= 92:
                    matched_group = idx
                    break
            if matched_group is not None:
                break

        if matched_group is not None:
            groups[matched_group].append(item)
        else:
            matched_group = len(groups)
            groups.append([item])

        # Register this item's key against the group it landed in, regardless
        # of whether it founded the group or joined via a near-dupe title —
        # otherwise a later item with the exact same key would fail to merge
        # (equivalence-closure gap).
        key_to_group[key] = matched_group

    survivors: list[RawItem] = []
    for group in groups:
        group.sort(key=lambda i: _tier(i.source_id))
        winner = group[0]
        mirrors = [str(i.url) for i in group[1:]]
        if mirrors:
            winner = winner.model_copy(
                update={"meta": {**winner.meta, "mirror_urls": mirrors}}
            )
        survivors.append(winner)
    return survivors


def prefilter(items: list[RawItem]) -> list[RawItem]:
    """Cheap cuts before spending any tokens. Target: 400+ -> ~120 items.

    Drop: no abstract, pure survey/benchmark-rehash titles, v2+ arXiv
    revisions already published in a prior issue (check data/seen.json).
    Auto-keep: tier 1 sources, anything with a CVE, HF upvotes >= 30.
    """
    seen = _load_seen()
    kept: list[RawItem] = []
    for item in items:
        if item.dedupe_key in seen:
            continue
        if _tier(item.source_id) == 1:
            kept.append(item)
            continue
        if item.meta.get("cve_ids"):
            kept.append(item)
            continue
        if item.meta.get("hf_upvotes", 0) >= 30:
            kept.append(item)
            continue
        if not item.summary.strip():
            continue
        kept.append(item)
    return kept


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
