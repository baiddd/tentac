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


def test_dedupe_mirror_urls_are_deduplicated_when_group_has_identical_urls(monkeypatch):
    """A paper cross-listed in multiple arXiv categories (e.g. cs.CL, cs.LG,
    cs.AI) is fetched once per category, producing several RawItems that all
    share the exact same URL (arXiv has no per-category URL). dedupe() must
    not list that one URL as a "mirror" once per duplicate group member.
    """
    tiers = {"hf-daily-papers": 1, "arxiv-cs-cl": 2, "arxiv-cs-lg": 2, "arxiv-cs-ai": 2}
    monkeypatch.setattr("score.SOURCE_TIERS", tiers)

    same_arxiv_url = "http://arxiv.org/abs/2608.19880v1"
    items = [
        _item("arxiv-cs-cl", same_arxiv_url, title="EnvHarness", arxiv_id="2608.19880v1"),
        _item("arxiv-cs-lg", same_arxiv_url, title="EnvHarness", arxiv_id="2608.19880v1"),
        _item("arxiv-cs-ai", same_arxiv_url, title="EnvHarness", arxiv_id="2608.19880v1"),
        _item(
            "hf-daily-papers",
            "https://huggingface.co/papers/2608.19880",
            title="EnvHarness",
            arxiv_id="2608.19880",
        ),
    ]
    result = dedupe(items)

    assert len(result) == 1
    assert result[0].source_id == "hf-daily-papers"
    assert result[0].meta["mirror_urls"] == [same_arxiv_url], (
        "the 3 identical arXiv-category URLs must collapse into one mirror entry, "
        f"got {result[0].meta['mirror_urls']!r}"
    )


def test_dedupe_mirror_urls_exclude_the_winners_own_url(monkeypatch):
    """A paper cross-listed in two arXiv categories, where the higher-tier
    "winner" is itself one of the arXiv entries (not e.g. hf-daily-papers),
    can end up with a mirror URL identical to its own url (arXiv has no
    per-category URL). Listing an item's own URL as its own "mirror" is
    wrong regardless of the intra-mirror dedup added above.
    """
    tiers = {"arxiv-cs-lg": 2, "arxiv-cs-ai": 2}
    monkeypatch.setattr("score.SOURCE_TIERS", tiers)

    same_arxiv_url = "http://arxiv.org/abs/2608.20574v1"
    items = [
        _item("arxiv-cs-lg", same_arxiv_url, title="FlavourBench", arxiv_id="2608.20574v1"),
        _item("arxiv-cs-ai", same_arxiv_url, title="FlavourBench", arxiv_id="2608.20574v1"),
    ]
    result = dedupe(items)

    assert len(result) == 1
    mirror_urls = result[0].meta.get("mirror_urls", [])
    assert mirror_urls == [], (
        "a mirror identical to the winner's own url must not be listed, "
        f"got {mirror_urls!r}"
    )


def test_dedupe_keeps_distinct_items():
    items = [_item("s1", "https://a.com/1", title="A"), _item("s2", "https://a.com/2", title="B")]
    result = dedupe(items)
    assert len(result) == 2


def test_dedupe_does_not_merge_title_subset_of_a_different_paper():
    """rapidfuzz.token_set_ratio scores a strict token-subset as 100, which
    would otherwise wrongly merge two distinct papers whenever one title's
    words are a subset of the other's (e.g. a report and its addendum).
    """
    items = [
        _item("s1", "https://a.com/1", title="GPT-4 Technical Report"),
        _item(
            "s2",
            "https://a.com/2",
            title="GPT-4 Technical Report Addendum: Safety Evaluations",
        ),
    ]
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
