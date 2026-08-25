import json
from unittest.mock import MagicMock, patch

from models import RawItem
from score import classify_and_score


def _item(url, title="A Paper", **meta):
    return RawItem(
        source_id="s",
        kind="paper",
        title=title,
        url=url,
        published_at="2026-08-18T00:00:00Z",
        summary="Abstract",
        meta=meta,
    )


def _fake_response(payload: list[dict]):
    response = MagicMock()
    response.content = [MagicMock(type="text", text=json.dumps(payload))]
    return response


@patch("score.Anthropic")
def test_classify_and_score_maps_valid_rows(mock_anthropic_cls):
    mock_client = MagicMock()
    mock_anthropic_cls.return_value = mock_client
    mock_client.messages.create.return_value = _fake_response(
        [
            {
                "url": "https://example.com/a",
                "section": "llm",
                "score": 0.8,
                "why": "Notably improves reasoning benchmarks.",
            }
        ]
    )

    items = [_item("https://example.com/a", mirror_urls=["https://mirror.com/a"])]
    result = classify_and_score(items)

    assert len(result) == 1
    scored = result[0]
    assert scored.section == "llm"
    assert scored.score == 0.8
    assert scored.why == "Notably improves reasoning benchmarks."
    assert str(scored.mirrors[0]) == "https://mirror.com/a"


@patch("score.Anthropic")
def test_classify_and_score_drops_invalid_section(mock_anthropic_cls):
    mock_client = MagicMock()
    mock_anthropic_cls.return_value = mock_client
    mock_client.messages.create.return_value = _fake_response(
        [
            {
                "url": "https://example.com/a",
                "section": "not-a-real-section",
                "score": 0.5,
                "why": "x",
            }
        ]
    )

    items = [_item("https://example.com/a")]
    result = classify_and_score(items)

    assert result == []


@patch("score.Anthropic")
def test_classify_and_score_batches_by_twenty(mock_anthropic_cls):
    mock_client = MagicMock()
    mock_anthropic_cls.return_value = mock_client
    mock_client.messages.create.return_value = _fake_response([])

    items = [_item(f"https://example.com/{i}") for i in range(45)]
    classify_and_score(items)

    assert mock_client.messages.create.call_count == 3
