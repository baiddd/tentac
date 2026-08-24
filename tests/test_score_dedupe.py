from models import RawItem
from score import dedupe


def _item(source_id, url, title="Same Paper", **meta):
    return RawItem(
        source_id=source_id,
        kind="paper",
        title=title,
        url=url,
        published_at="2026-08-18T00:00:00Z",
        meta=meta,
    )


def test_dedupe_collapses_exact_key_keeps_highest_tier_source(monkeypatch):
    tiers = {"hf-daily-papers": 1, "arxiv-cs-cl": 2}
    monkeypatch.setattr("score.SOURCE_TIERS", tiers)

    items = [
        _item("arxiv-cs-cl", "https://arxiv.org/abs/2508.01234", arxiv_id="2508.01234"),
        _item("hf-daily-papers", "https://huggingface.co/papers/2508.01234", arxiv_id="2508.01234"),
    ]
    result = dedupe(items)

    assert len(result) == 1
    assert result[0].source_id == "hf-daily-papers"
    assert result[0].meta["mirror_urls"] == ["https://arxiv.org/abs/2508.01234"]


def test_dedupe_collapses_near_dupe_titles(monkeypatch):
    monkeypatch.setattr("score.SOURCE_TIERS", {"lab-blog": 1, "news-site": 3})
    items = [
        _item("lab-blog", "https://lab.com/a", title="New Model Beats Benchmark Records"),
        _item("news-site", "https://news.com/a", title="new model beats benchmark records!"),
    ]
    result = dedupe(items)
    assert len(result) == 1
    assert result[0].source_id == "lab-blog"


def test_dedupe_keeps_distinct_items():
    items = [_item("s1", "https://a.com/1", title="A"), _item("s2", "https://a.com/2", title="B")]
    result = dedupe(items)
    assert len(result) == 2
