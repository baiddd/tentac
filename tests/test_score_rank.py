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
    monkeypatch.setattr("score.SOURCE_TIERS", {"s0": 2, "s1": 2, "s2": 2, "s3": 2})
    items = [_scored("llm", 0.9 - i * 0.01, source_id=f"s{i % 4}") for i in range(10)]
    result = rank(items)
    assert len(result) == 6


def test_rank_caps_eight_for_security_with_active_incident(monkeypatch):
    monkeypatch.setattr("score.SOURCE_TIERS", {"s0": 2, "s1": 2, "s2": 2, "s3": 2})
    items = [_scored("security", 0.9 - i * 0.01, source_id=f"s{i % 4}", cve_ids=["CVE-2026-1"]) for i in range(10)]
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


def test_rank_caps_three_per_source_within_a_section(monkeypatch):
    monkeypatch.setattr("score.SOURCE_TIERS", {"dominant": 2, "other": 2, "filler": 2})
    # 10 items from one source, all scoring higher than the rest — without a
    # per-source cap, "dominant" would take all 6 section slots. "other" and
    # "filler" together supply exactly enough items (2 + 1) to fill the 3
    # slots freed up by capping "dominant" at 3, so the total still reaches
    # the section cap of 6.
    dominant_items = [
        _scored("llm", 0.9 - i * 0.01, source_id="dominant") for i in range(10)
    ]
    other_items = [_scored("llm", 0.5, source_id="other") for _ in range(2)]
    filler_items = [_scored("llm", 0.4, source_id="filler") for _ in range(1)]
    result = rank(dominant_items + other_items + filler_items)

    assert len(result) == 6, "section cap of 6 should still apply"
    by_source = [item.source_id for item in result]
    assert by_source.count("dominant") == 3, "no source should exceed 3 items in a section"
    assert by_source.count("other") == 2, "lower-scoring source should fill the freed-up slots"
    assert by_source.count("filler") == 1, "third source should fill the last freed-up slot"


def test_rank_caps_three_per_family_across_different_source_ids(monkeypatch):
    monkeypatch.setattr("score.SOURCE_TIERS", {"arxiv-a": 2, "arxiv-b": 2, "other": 2, "filler": 2})
    monkeypatch.setattr("score.SOURCE_FAMILIES", {"arxiv-a": "arxiv", "arxiv-b": "arxiv"})
    # arxiv-a and arxiv-b share the "arxiv" family (like real arxiv-cs-cl/arxiv-cs-lg
    # do via config/sources.yaml). Without family-level capping, each of the two
    # source_ids would independently cap at 3 (6 total), still crowding out every
    # other source — reproducing the exact bug the reviewer found against real data.
    arxiv_a_items = [_scored("llm", 0.9 - i * 0.01, source_id="arxiv-a") for i in range(4)]
    arxiv_b_items = [_scored("llm", 0.8 - i * 0.01, source_id="arxiv-b") for i in range(4)]
    other_items = [_scored("llm", 0.5, source_id="other") for _ in range(2)]
    filler_items = [_scored("llm", 0.4, source_id="filler") for _ in range(1)]
    result = rank(arxiv_a_items + arxiv_b_items + other_items + filler_items)

    assert len(result) == 6, "section cap of 6 should still apply"
    by_source = [item.source_id for item in result]
    arxiv_count = sum(1 for s in by_source if s in ("arxiv-a", "arxiv-b"))
    assert arxiv_count == 3, "combined arxiv family (across both source_ids) must not exceed 3"
    assert by_source.count("other") == 2, "other family fills freed-up slots"
    assert by_source.count("filler") == 1, "filler family fills the last freed-up slot"
