from models import RawItem
from score import prefilter


def _item(source_id, title, summary="An abstract.", **meta):
    return RawItem(
        source_id=source_id,
        kind="paper",
        title=title,
        url=f"https://example.com/{title.replace(' ', '-')}",
        published_at="2026-08-18T00:00:00Z",
        summary=summary,
        meta=meta,
    )


def test_prefilter_drops_empty_summary(monkeypatch):
    monkeypatch.setattr("score.SOURCE_TIERS", {"s": 2})
    monkeypatch.setattr("score._load_seen", lambda: set())
    items = [_item("s", "No abstract", summary="")]
    assert prefilter(items) == []


def test_prefilter_auto_keeps_tier1_even_without_summary(monkeypatch):
    monkeypatch.setattr("score.SOURCE_TIERS", {"tier1-src": 1})
    monkeypatch.setattr("score._load_seen", lambda: set())
    items = [_item("tier1-src", "Tier 1 item", summary="")]
    assert len(prefilter(items)) == 1


def test_prefilter_auto_keeps_cve_items(monkeypatch):
    monkeypatch.setattr("score.SOURCE_TIERS", {"s": 3})
    monkeypatch.setattr("score._load_seen", lambda: set())
    items = [_item("s", "Vuln", summary="", cve_ids=["CVE-2026-1"])]
    assert len(prefilter(items)) == 1


def test_prefilter_auto_keeps_high_hf_upvotes(monkeypatch):
    monkeypatch.setattr("score.SOURCE_TIERS", {"s": 3})
    monkeypatch.setattr("score._load_seen", lambda: set())
    items = [_item("s", "Popular", summary="", hf_upvotes=31)]
    assert len(prefilter(items)) == 1


def test_prefilter_drops_already_seen_arxiv_revision(monkeypatch):
    monkeypatch.setattr("score.SOURCE_TIERS", {"s": 2})
    monkeypatch.setattr("score._load_seen", lambda: {"arxiv:2508.01234"})
    items = [_item("s", "Revised paper", arxiv_id="2508.01234v3")]
    assert prefilter(items) == []


def test_prefilter_drops_tier2_item_with_no_relevance_keyword(monkeypatch):
    monkeypatch.setattr("score.SOURCE_TIERS", {"s": 2})
    monkeypatch.setattr("score._load_seen", lambda: set())
    monkeypatch.setattr("score.RELEVANCE_KEYWORDS", ["large language model"])
    items = [_item("s", "A Study of Crop Yield Prediction with Random Forests")]
    assert prefilter(items) == []


def test_prefilter_keeps_tier2_item_matching_relevance_keyword(monkeypatch):
    monkeypatch.setattr("score.SOURCE_TIERS", {"s": 2})
    monkeypatch.setattr("score._load_seen", lambda: set())
    monkeypatch.setattr("score.RELEVANCE_KEYWORDS", ["large language model"])
    items = [_item("s", "Scaling a Large Language Model for Code Repair")]
    assert len(prefilter(items)) == 1


def test_prefilter_relevance_keyword_matches_title_not_summary(monkeypatch):
    monkeypatch.setattr("score.SOURCE_TIERS", {"s": 2})
    monkeypatch.setattr("score._load_seen", lambda: set())
    monkeypatch.setattr("score.RELEVANCE_KEYWORDS", ["large language model"])
    items = [
        _item(
            "s",
            "Crop Yield Prediction with Random Forests",
            summary="We compare against a large language model baseline.",
        )
    ]
    assert prefilter(items) == []


def test_load_relevance_keywords_from_real_config_is_nonempty():
    """Regression guard: the actual config/sources.yaml must define
    relevance_keywords, or every tier-2/3 arXiv item silently passes
    prefilter unfiltered again (the exact bug this filter fixes)."""
    from score import _load_relevance_keywords

    keywords = _load_relevance_keywords()
    assert len(keywords) >= 10
