import json
from pathlib import Path

import pytest

import fetch
from models import RawItem


def _item(source_id: str, url: str) -> RawItem:
    return RawItem(
        source_id=source_id,
        kind="article",
        title=f"Item from {source_id}",
        url=url,
        published_at="2026-08-18T00:00:00Z",
    )


def test_main_writes_jsonl_and_survives_one_dead_source(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "sources.yaml").write_text(
        """
papers:
  - id: good-source
    kind: rss
    url: https://example.com/feed.xml
    tier: 1
    sections: [llm]
  - id: dead-source
    kind: rss
    url: https://example.com/dead.xml
    tier: 2
    sections: [llm]
"""
    )

    def fake_fetch_rss(source, since, until):
        if source["id"] == "dead-source":
            raise ConnectionError("boom")
        return [_item(source["id"], "https://example.com/a")]

    monkeypatch.setattr(fetch, "FETCHERS", {**fetch.FETCHERS, "rss": fake_fetch_rss})
    monkeypatch.setattr(fetch.sys, "argv", ["fetch.py", "--week", "2026-W34"])

    fetch.main()

    out_path = tmp_path / "data" / "raw" / "2026-W34.jsonl"
    lines = out_path.read_text().splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["source_id"] == "good-source"

    captured = capsys.readouterr()
    assert "dead-source" in captured.out
    assert "boom" in captured.out
