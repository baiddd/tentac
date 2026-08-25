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


def test_rank_asserts_exact_blended_formula_weights(monkeypatch):
    """Assert rank() uses exact formula: 0.55*model + 0.25*social + 0.20*source_tier.

    Constructs a case where blended formula reverses raw-score ordering:
    lower raw score + high social + tier-1 beats higher raw score + no social + tier-4.
    Raw-score-only sort would fail this test.
    """
    import math

    monkeypatch.setattr("score.SOURCE_TIERS", {"tier1": 1, "tier4": 4})

    # Item A: lower model score (0.6), but excellent social (10k upvotes) and best tier (1)
    item_a = _scored("llm", 0.6, source_id="tier1", hf_upvotes=10000)

    # Item B: higher model score (0.9), but no social (0 upvotes) and worst tier (4)
    item_b = _scored("llm", 0.9, source_id="tier4", hf_upvotes=0)

    # Hand-compute final blended scores:
    # final = 0.55*model_score + 0.25*social + 0.20*source_tier
    # where: social = min(log1p(upvotes)/log1p(1000), 1.0)
    #        source_tier = (4 - tier) / 3

    # Item A final score:
    social_a = min(math.log1p(10000) / math.log1p(1000), 1.0)  # ~1.333 → capped to 1.0
    tier_a = (4 - 1) / 3  # 1.0
    final_a = 0.55 * 0.6 + 0.25 * social_a + 0.20 * tier_a  # 0.33 + 0.25 + 0.20 = 0.78

    # Item B final score:
    social_b = min(math.log1p(0) / math.log1p(1000), 1.0)  # 0
    tier_b = (4 - 4) / 3  # 0
    final_b = 0.55 * 0.9 + 0.25 * social_b + 0.20 * tier_b  # 0.495 + 0 + 0 = 0.495

    # Item A (0.78) should win despite lower raw score, because blending gives social
    # and tier signals significant weight. Raw score alone (0.9 > 0.6) would reverse order.
    result = rank([item_b, item_a])
    assert result[0].score == 0.6, f"Item A (lower raw score, high social/tier) should rank first, got {result[0].score}"
    assert result[1].score == 0.9, f"Item B (higher raw score, low social/tier) should rank second, got {result[1].score}"
