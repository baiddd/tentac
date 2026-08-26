from datetime import datetime, timezone

import httpx
import respx

from fetch import fetch_the_batch

LISTING_HTML = """
<html><head>
<script type="application/ld+json">{"@context":"https://schema.org","@type":"CollectionPage","name":"Machine Learning Research","mainEntity":{"@type":"ItemList","itemListElement":[{"@type":"ListItem","position":1,"url":"https://www.deeplearning.ai/the-batch/agents-come-to-speech-recognition","name":"Agents Come to Speech Recognition: AgenticASR incorporates user corrections"},{"@type":"ListItem","position":2,"url":"https://www.deeplearning.ai/the-batch/an-old-article","name":"An Old Article: from outside the window"}]}}</script>
</head><body>ignored</body></html>
"""

NEW_ARTICLE_HTML = """
<html><head>
<script type="application/ld+json">{"@context":"https://schema.org","@type":"NewsArticle","headline":"Agents Come to Speech Recognition","datePublished":"2026-08-21T08:15:03.000-07:00"}</script>
</head><body>ignored</body></html>
"""

OLD_ARTICLE_HTML = """
<html><head>
<script type="application/ld+json">{"@context":"https://schema.org","@type":"NewsArticle","headline":"An Old Article","datePublished":"2026-01-01T00:00:00.000-07:00"}</script>
</head><body>ignored</body></html>
"""


@respx.mock
def test_fetch_the_batch_parses_listing_and_article_dates():
    respx.get("https://www.deeplearning.ai/the-batch/tag/research").mock(
        return_value=httpx.Response(200, text=LISTING_HTML)
    )
    respx.get("https://www.deeplearning.ai/the-batch/agents-come-to-speech-recognition").mock(
        return_value=httpx.Response(200, text=NEW_ARTICLE_HTML)
    )
    respx.get("https://www.deeplearning.ai/the-batch/an-old-article").mock(
        return_value=httpx.Response(200, text=OLD_ARTICLE_HTML)
    )
    source = {"id": "the-batch", "url": "https://www.deeplearning.ai/the-batch/tag/research"}
    since = datetime(2026, 8, 17, tzinfo=timezone.utc)
    until = datetime(2026, 8, 24, tzinfo=timezone.utc)

    items = fetch_the_batch(source, since, until)

    assert len(items) == 1, "the old article (2026-01-01) must be filtered out by the since/until window"
    assert items[0].source_id == "the-batch"
    assert items[0].kind == "article"
    assert items[0].title == "Agents Come to Speech Recognition: AgenticASR incorporates user corrections"
    assert str(items[0].url) == "https://www.deeplearning.ai/the-batch/agents-come-to-speech-recognition"
    assert items[0].published_at == datetime.fromisoformat("2026-08-21T08:15:03.000-07:00")


@respx.mock
def test_fetch_the_batch_returns_empty_list_when_no_ld_json_found():
    respx.get("https://www.deeplearning.ai/the-batch/tag/research").mock(
        return_value=httpx.Response(200, text="<html><body>no structured data here</body></html>")
    )
    source = {"id": "the-batch", "url": "https://www.deeplearning.ai/the-batch/tag/research"}
    since = datetime(2026, 8, 17, tzinfo=timezone.utc)
    until = datetime(2026, 8, 24, tzinfo=timezone.utc)

    items = fetch_the_batch(source, since, until)

    assert items == []


@respx.mock
def test_fetch_the_batch_skips_one_bad_article_and_keeps_the_rest():
    respx.get("https://www.deeplearning.ai/the-batch/tag/research").mock(
        return_value=httpx.Response(200, text=LISTING_HTML)
    )
    respx.get("https://www.deeplearning.ai/the-batch/agents-come-to-speech-recognition").mock(
        return_value=httpx.Response(404)
    )
    respx.get("https://www.deeplearning.ai/the-batch/an-old-article").mock(
        return_value=httpx.Response(200, text=NEW_ARTICLE_HTML.replace("An Old Article", "Renamed Article"))
    )
    source = {"id": "the-batch", "url": "https://www.deeplearning.ai/the-batch/tag/research"}
    since = datetime(2026, 8, 17, tzinfo=timezone.utc)
    until = datetime(2026, 8, 24, tzinfo=timezone.utc)

    items = fetch_the_batch(source, since, until)

    assert len(items) == 1, "the 404'd article must be skipped, not raised, and must not discard the good one"
    assert items[0].source_id == "the-batch"


@respx.mock
def test_fetch_the_batch_skips_article_with_naive_datetime():
    respx.get("https://www.deeplearning.ai/the-batch/tag/research").mock(
        return_value=httpx.Response(200, text=LISTING_HTML)
    )
    naive_article_html = """
<html><head>
<script type="application/ld+json">{"@context":"https://schema.org","@type":"NewsArticle","headline":"Agents Come to Speech Recognition","datePublished":"2026-08-21T08:15:03"}</script>
</head><body>ignored</body></html>
"""
    respx.get("https://www.deeplearning.ai/the-batch/agents-come-to-speech-recognition").mock(
        return_value=httpx.Response(200, text=naive_article_html)
    )
    respx.get("https://www.deeplearning.ai/the-batch/an-old-article").mock(
        return_value=httpx.Response(200, text=OLD_ARTICLE_HTML)
    )
    source = {"id": "the-batch", "url": "https://www.deeplearning.ai/the-batch/tag/research"}
    since = datetime(2026, 8, 17, tzinfo=timezone.utc)
    until = datetime(2026, 8, 24, tzinfo=timezone.utc)

    items = fetch_the_batch(source, since, until)

    assert items == [], "a naive (no tz offset) datePublished must be excluded, not crash the window comparison"
