from models import ScoredItem
from score import rank


def _scored(section, score, source_id="s", **meta):
    return ScoredItem(
        source_id=source_id,
        kind="paper",
        title=f"Item {score}",
        url=f"https://example.com/{section}-{score}-{source_id}",
        published_at="2026-08-18T00:00:00Z",
        section=section,
        score=score,
        why="why",
        meta=meta,
    )


def test_rank_caps_six_per_section(monkeypatch):
    monkeypatch.setattr("score.SOURCE_TIERS", {"s": 2})
    items = [_scored("llm", 0.9 - i * 0.01) for i in range(10)]
    result = rank(items)
    assert len(result) == 6


def test_rank_caps_eight_for_security_with_active_incident(monkeypatch):
    monkeypatch.setattr("score.SOURCE_TIERS", {"s": 2})
    items = [_scored("security", 0.9 - i * 0.01, cve_ids=["CVE-2026-1"]) for i in range(10)]
    result = rank(items)
    assert len(result) == 8


def test_rank_orders_by_blended_score_descending(monkeypatch):
    monkeypatch.setattr("score.SOURCE_TIERS", {"tier1": 1, "tier3": 3})
    low_score_tier1 = _scored("llm", 0.5, source_id="tier1")
    high_score_tier3 = _scored("llm", 0.9, source_id="tier3")
    result = rank([high_score_tier3, low_score_tier1])
    # source_tier component should pull tier-1 above a much higher raw score
    # only when scores are close; here 0.9 vs 0.5 model_score dominates.
    assert result[0].score == 0.9


def test_rank_empty_section_returns_empty_list(monkeypatch):
    monkeypatch.setattr("score.SOURCE_TIERS", {"s": 2})
    assert rank([]) == []
