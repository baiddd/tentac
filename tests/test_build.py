import json
from unittest.mock import MagicMock, patch

from models import ScoredItem
from build import write_headline, build_issue


def _scored(section, score, title="Item"):
    return ScoredItem(
        source_id="s",
        kind="paper",
        title=title,
        url=f"https://example.com/{section}-{title}".replace(" ", "-"),
        published_at="2026-08-18T00:00:00Z",
        section=section,
        score=score,
        why="why line",
    )


@patch("build.Anthropic")
def test_write_headline_returns_model_text(mock_anthropic_cls):
    mock_client = MagicMock()
    mock_anthropic_cls.return_value = mock_client
    response = MagicMock()
    response.content = [MagicMock(type="text", text="A quiet week for new releases.")]
    mock_client.messages.create.return_value = response

    items = [_scored("llm", 0.9)]
    assert write_headline(items) == "A quiet week for new releases."


@patch("build.Anthropic")
def test_write_headline_handles_no_items(mock_anthropic_cls):
    mock_client = MagicMock()
    mock_anthropic_cls.return_value = mock_client
    response = MagicMock()
    response.content = [MagicMock(type="text", text="It was a quiet week.")]
    mock_client.messages.create.return_value = response

    assert write_headline([]) == "It was a quiet week."
    mock_client.messages.create.assert_called_once()


def test_build_issue_groups_by_section_and_sets_bounds(monkeypatch):
    monkeypatch.setattr(
        "build._section_meta",
        lambda: {
            "llm": {"label": "LLM & reasoning", "blurb": "Models, training, benchmarks, agents"},
            "security": {"label": "AI security", "blurb": "Supply chain, prompt injection"},
        },
    )
    items = [_scored("llm", 0.9, "Alpha"), _scored("llm", 0.7, "Beta")]
    with patch("build.write_headline", return_value="Steady progress this week."):
        issue = build_issue("2026-W34", items)

    assert issue.week == "2026-W34"
    assert issue.headline == "Steady progress this week."
    section_ids = [s.id for s in issue.sections]
    assert "llm" in section_ids
    assert "security" not in section_ids  # no items -> quiet week -> omitted, not padded
    llm_section = next(s for s in issue.sections if s.id == "llm")
    assert len(llm_section.items) == 2
    assert issue.stats["items_kept"] == 2


def test_build_issue_uses_given_headline_without_calling_write_headline(monkeypatch):
    monkeypatch.setattr(
        "build._section_meta",
        lambda: {"llm": {"label": "LLM & reasoning", "blurb": "Models, training, benchmarks, agents"}},
    )
    items = [_scored("llm", 0.9, "Alpha")]
    with patch("build.write_headline") as mock_write_headline:
        issue = build_issue("2026-W34", items, headline="Supplied by Claude Code locally.")

    assert issue.headline == "Supplied by Claude Code locally."
    mock_write_headline.assert_not_called()


def test_build_issue_records_analyzed_by_in_stats(monkeypatch):
    monkeypatch.setattr(
        "build._section_meta",
        lambda: {"llm": {"label": "LLM & reasoning", "blurb": "Models, training, benchmarks, agents"}},
    )
    items = [_scored("llm", 0.9, "Alpha")]
    issue = build_issue("2026-W34", items, headline="h", analyzed_by="claude-sonnet-5")

    assert issue.stats["analyzed_by"] == "claude-sonnet-5"


def test_build_issue_applies_section_summaries(monkeypatch):
    monkeypatch.setattr(
        "build._section_meta",
        lambda: {
            "llm": {"label": "LLM & reasoning", "blurb": "Models, training, benchmarks, agents"},
            "security": {"label": "AI security", "blurb": "Supply chain, prompt injection"},
        },
    )
    items = [_scored("llm", 0.9, "Alpha")]
    issue = build_issue(
        "2026-W34", items, headline="h", section_summaries={"llm": "A quiet week for new releases."}
    )

    llm_section = next(s for s in issue.sections if s.id == "llm")
    assert llm_section.summary == "A quiet week for new releases."


def test_build_issue_defaults_summary_to_empty_string(monkeypatch):
    monkeypatch.setattr(
        "build._section_meta",
        lambda: {"llm": {"label": "LLM & reasoning", "blurb": "Models, training, benchmarks, agents"}},
    )
    items = [_scored("llm", 0.9, "Alpha")]
    issue = build_issue("2026-W34", items, headline="h")

    assert issue.sections[0].summary == ""
