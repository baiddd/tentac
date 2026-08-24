from datetime import datetime, timezone

import respx
import httpx

from fetch import fetch_hf_daily

DAY_RESPONSE = [
    {
        "paper": {"id": "2508.01234", "title": "HF Paper", "summary": "Abstract"},
        "publishedAt": "2026-08-18T09:00:00.000Z",
        "upvotes": 42,
    }
]


@respx.mock
def test_fetch_hf_daily_one_day_in_window():
    respx.get(
        "https://huggingface.co/api/daily_papers", params={"date": "2026-08-18"}
    ).mock(return_value=httpx.Response(200, json=DAY_RESPONSE))
    respx.get(url__regex=r"https://huggingface.co/api/daily_papers\?date=2026-08-(?!18).*").mock(
        return_value=httpx.Response(200, json=[])
    )

    source = {"id": "hf-daily-papers", "url": "https://huggingface.co/api/daily_papers"}
    since = datetime(2026, 8, 17, tzinfo=timezone.utc)
    until = datetime(2026, 8, 19, tzinfo=timezone.utc)

    items = fetch_hf_daily(source, since, until)

    assert len(items) == 1
    item = items[0]
    assert item.title == "HF Paper"
    assert item.meta["hf_upvotes"] == 42
    assert item.meta["arxiv_id"] == "2508.01234"
    assert str(item.url) == "https://huggingface.co/papers/2508.01234"
