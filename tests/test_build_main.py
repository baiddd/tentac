import json
from unittest.mock import patch

import build


_SOURCES_YAML = (
    "sections:\n"
    "  - id: llm\n"
    '    label: "LLM & reasoning"\n'
    '    blurb: "Models, training, benchmarks, agents"\n'
)


def _write_sources_yaml(tmp_path):
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "sources.yaml").write_text(_SOURCES_YAML)


def test_main_writes_issue_index_and_seen(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _write_sources_yaml(tmp_path)
    (tmp_path / "data" / "scored").mkdir(parents=True)
    scored_item = {
        "source_id": "s",
        "kind": "paper",
        "title": "A Paper",
        "url": "https://example.com/a",
        "published_at": "2026-08-18T00:00:00Z",
        "summary": "",
        "authors": [],
        "meta": {"arxiv_id": "2508.01234"},
        "section": "llm",
        "score": 0.9,
        "why": "why line",
        "mirrors": [],
    }
    (tmp_path / "data" / "scored" / "2026-W34.jsonl").write_text(json.dumps(scored_item) + "\n")

    with patch("build.write_headline", return_value="Notable week."):
        monkeypatch.setattr("sys.argv", ["build.py", "--week", "2026-W34"])
        build.main()

    issue = json.loads((tmp_path / "data" / "2026-W34.json").read_text())
    assert issue["week"] == "2026-W34"
    assert issue["headline"] == "Notable week."

    index = json.loads((tmp_path / "data" / "index.json").read_text())
    assert index[0]["week"] == "2026-W34"

    seen = json.loads((tmp_path / "data" / "seen.json").read_text())
    assert "arxiv:2508.01234" in seen


def test_main_is_atomic_no_tmp_file_left_behind(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _write_sources_yaml(tmp_path)
    (tmp_path / "data" / "scored").mkdir(parents=True)
    (tmp_path / "data" / "scored" / "2026-W35.jsonl").write_text("")

    with patch("build.write_headline", return_value="Quiet week."):
        monkeypatch.setattr("sys.argv", ["build.py", "--week", "2026-W35"])
        build.main()

    assert not (tmp_path / "data" / ".2026-W35.json.tmp").exists()
    assert (tmp_path / "data" / "2026-W35.json").exists()


def test_main_headline_flag_skips_write_headline(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _write_sources_yaml(tmp_path)
    (tmp_path / "data" / "scored").mkdir(parents=True)
    (tmp_path / "data" / "scored" / "2026-W34.jsonl").write_text("")

    with patch("build.write_headline") as mock_write_headline:
        monkeypatch.setattr(
            "sys.argv", ["build.py", "--week", "2026-W34", "--headline", "Written by Claude Code."]
        )
        build.main()

    mock_write_headline.assert_not_called()
    issue = json.loads((tmp_path / "data" / "2026-W34.json").read_text())
    assert issue["headline"] == "Written by Claude Code."


def test_main_accepts_date_instead_of_week(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _write_sources_yaml(tmp_path)
    (tmp_path / "data" / "scored").mkdir(parents=True)
    # 2026-08-24 falls in ISO week 2026-W35.
    (tmp_path / "data" / "scored" / "2026-W35.jsonl").write_text("")

    with patch("build.write_headline", return_value="Quiet week."):
        monkeypatch.setattr("sys.argv", ["build.py", "--date", "2026-08-24"])
        build.main()

    assert (tmp_path / "data" / "2026-W35.json").exists()


def test_main_section_summaries_flag(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _write_sources_yaml(tmp_path)
    (tmp_path / "data" / "scored").mkdir(parents=True)
    scored_item = {
        "source_id": "s",
        "kind": "paper",
        "title": "A Paper",
        "url": "https://example.com/a",
        "published_at": "2026-08-18T00:00:00Z",
        "summary": "",
        "authors": [],
        "meta": {},
        "section": "llm",
        "score": 0.9,
        "why": "why line",
        "mirrors": [],
    }
    (tmp_path / "data" / "scored" / "2026-W34.jsonl").write_text(json.dumps(scored_item) + "\n")

    monkeypatch.setattr(
        "sys.argv",
        [
            "build.py",
            "--week",
            "2026-W34",
            "--headline",
            "h",
            "--section-summaries",
            '{"llm": "A quiet week for new releases."}',
        ],
    )
    build.main()

    issue = json.loads((tmp_path / "data" / "2026-W34.json").read_text())
    llm_section = next(s for s in issue["sections"] if s["id"] == "llm")
    assert llm_section["summary"] == "A quiet week for new releases."
