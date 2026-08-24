from datetime import datetime, timezone

import respx
import httpx

from fetch import fetch_openreview


@respx.mock
def test_fetch_openreview_empty_is_normal():
    respx.get("https://api2.openreview.net/notes?invitation=NeurIPS.cc%2F-%2FDecision&limit=1000").mock(
        return_value=httpx.Response(200, json={"notes": []})
    )
    source = {
        "id": "openreview",
        "url": "https://api2.openreview.net/notes",
        "venues": ["NeurIPS.cc"],
    }
    since = datetime(2026, 8, 17, tzinfo=timezone.utc)
    until = datetime(2026, 8, 24, tzinfo=timezone.utc)

    assert fetch_openreview(source, since, until) == []


@respx.mock
def test_fetch_openreview_maps_a_decision_note():
    respx.get("https://api2.openreview.net/notes?invitation=NeurIPS.cc%2F-%2FDecision&limit=1000").mock(
        return_value=httpx.Response(
            200,
            json={
                "notes": [
                    {
                        "id": "abc123",
                        "content": {"title": {"value": "Accepted Paper"}},
                        "cdate": 1787097600000,  # 2026-08-19T00:00:00Z in ms
                        "invitation": "NeurIPS.cc/2026/Conference/-/Decision",
                    }
                ]
            },
        )
    )
    source = {
        "id": "openreview",
        "url": "https://api2.openreview.net/notes",
        "venues": ["NeurIPS.cc"],
    }
    since = datetime(2026, 8, 17, tzinfo=timezone.utc)
    until = datetime(2026, 8, 24, tzinfo=timezone.utc)

    items = fetch_openreview(source, since, until)
    assert len(items) == 1
    assert items[0].title == "Accepted Paper"
    assert str(items[0].url) == "https://openreview.net/forum?id=abc123"
