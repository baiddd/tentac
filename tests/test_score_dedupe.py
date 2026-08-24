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


def test_dedupe_transitive_chain_collapses_via_equivalence_closure():
    """A founds a group by dedupe_key. B has a *different* key but a
    near-dupe title, so it joins A's group via the title path. C shares
    B's exact dedupe_key but has a title that does NOT near-dupe-match
    A's (the group founder). All three must still collapse into one
    group, because B's key must have been registered when it joined —
    C is identity-equal to B by the exact-key rule even though C's
    title alone would never match A's.
    """
    item_a = _item(
        "arxiv-cs-cl",
        "https://arxiv.org/abs/1111.11111",
        title="Foo: A Novel Architecture",
        arxiv_id="1111.11111",
    )
    item_b = _item(
        "news-site",
        "https://news.example.com/story",
        title="Foo A Novel Architecture",
    )
    item_c = _item(
        "news-site",
        "https://news.example.com/story",
        title="Completely Unrelated Headline About Something Else",
    )

    result = dedupe([item_a, item_b, item_c])

    assert len(result) == 1
