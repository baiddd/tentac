from models import RawItem


def _item(**overrides) -> RawItem:
    base = dict(
        source_id="arxiv-cs-cl",
        kind="paper",
        title="A Paper",
        url="https://arxiv.org/abs/2508.01234v2",
        published_at="2026-08-18T00:00:00Z",
        meta={},
    )
    base.update(overrides)
    return RawItem(**base)


def test_dedupe_key_prefers_doi():
    item = _item(meta={"doi": "10.1038/s41586-026-00001-x", "arxiv_id": "2508.01234"})
    assert item.dedupe_key == "doi:10.1038/s41586-026-00001-x"


def test_dedupe_key_prefers_arxiv_over_url():
    item = _item(meta={"arxiv_id": "2508.01234v2"})
    assert item.dedupe_key == "arxiv:2508.01234"


def test_dedupe_key_prefers_cve_over_url():
    item = _item(
        url="https://example.com/blog/post",
        meta={"cve_ids": ["CVE-2026-12345"]},
    )
    assert item.dedupe_key == "cve:CVE-2026-12345"


def test_dedupe_key_normalizes_url_strips_utm_www_trailing_slash():
    item = _item(
        url="https://www.example.com/blog/post/?utm_source=x&utm_medium=y",
        meta={},
    )
    assert item.dedupe_key == "url:https://example.com/blog/post"


def test_dedupe_key_falls_back_to_url_when_no_ids():
    item = _item(url="https://example.com/a", meta={})
    assert item.dedupe_key == "url:https://example.com/a"
