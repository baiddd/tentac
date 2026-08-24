"""Stage 1 — collect. Reads config/sources.yaml, writes data/raw/<week>.jsonl.

Rules:
  - Never let one dead feed kill the run. Catch per-source, log, continue.
  - Cache by ETag / Last-Modified in .cache/ so reruns are cheap.
  - Window is [monday 00:00 UTC, next monday 00:00 UTC).
  - This stage does NOT filter on quality. It only filters on the date window
    and on a source's declared filter_keywords.
"""

from __future__ import annotations

import argparse
import time
from datetime import datetime, timedelta, timezone

from models import RawItem


def fetch_rss(source: dict, since: datetime, until: datetime) -> list[RawItem]:
    """feedparser. Fall back to <updated> when <published> is missing."""
    import feedparser
    import httpx

    response = httpx.get(source["url"], follow_redirects=True, timeout=30)
    response.raise_for_status()
    parsed = feedparser.parse(response.text)
    items: list[RawItem] = []
    for entry in parsed.entries:
        time_struct = entry.get("published_parsed") or entry.get("updated_parsed")
        if not time_struct:
            continue
        published_at = datetime(*time_struct[:6], tzinfo=timezone.utc)
        if not (since <= published_at < until):
            continue
        items.append(
            RawItem(
                source_id=source["id"],
                kind="article",
                title=entry.get("title", ""),
                url=entry.get("link"),
                published_at=published_at,
                summary=entry.get("summary", ""),
            )
        )
    return items


def fetch_arxiv(source: dict, since: datetime, until: datetime) -> list[RawItem]:
    """arXiv API: http://export.arxiv.org/api/query

    search_query=cat:cs.CL, sortBy=submittedDate, sortOrder=descending.
    Paginate 100 at a time until published_at < since.
    Rate limit: sleep 3s between calls. arXiv will block you otherwise.
    """
    import feedparser
    import httpx

    items: list[RawItem] = []
    start = 0
    page_size = 100
    while True:
        response = httpx.get(
            "http://export.arxiv.org/api/query",
            params={
                "search_query": f"cat:{source['category']}",
                "sortBy": "submittedDate",
                "sortOrder": "descending",
                "start": start,
                "max_results": page_size,
            },
            follow_redirects=True,
            timeout=30,
        )
        response.raise_for_status()
        parsed = feedparser.parse(response.text)
        if not parsed.entries:
            break

        stop = False
        for entry in parsed.entries:
            published_at = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
            if published_at < since:
                stop = True
                break
            if published_at >= until:
                continue
            arxiv_id = entry.id.rsplit("/abs/", 1)[-1]
            items.append(
                RawItem(
                    source_id=source["id"],
                    kind="paper",
                    title=entry.title,
                    url=entry.id,
                    published_at=published_at,
                    summary=entry.get("summary", ""),
                    authors=[a.name for a in entry.get("authors", [])],
                    meta={"arxiv_id": arxiv_id},
                )
            )
        if stop or len(parsed.entries) < page_size:
            break
        start += page_size
        time.sleep(3)
    return items


def fetch_hf_daily(source: dict, since: datetime, until: datetime) -> list[RawItem]:
    """GET /api/daily_papers?date=YYYY-MM-DD per day in the window.

    Keep paper.upvotes and paper.id in meta — score.py needs both.
    """
    import httpx

    items: list[RawItem] = []
    day = since
    while day < until:
        response = httpx.get(
            source["url"], params={"date": day.strftime("%Y-%m-%d")}, follow_redirects=True, timeout=30
        )
        response.raise_for_status()
        for entry in response.json():
            published_at = datetime.fromisoformat(
                entry["publishedAt"].replace("Z", "+00:00")
            )
            if not (since <= published_at < until):
                continue
            paper = entry["paper"]
            items.append(
                RawItem(
                    source_id=source["id"],
                    kind="paper",
                    title=paper["title"],
                    url=f"https://huggingface.co/papers/{paper['id']}",
                    published_at=published_at,
                    summary=paper.get("summary", ""),
                    meta={"arxiv_id": paper["id"], "hf_upvotes": entry.get("upvotes", 0)},
                )
            )
        day += timedelta(days=1)
    return items


def fetch_openreview(source: dict, since: datetime, until: datetime) -> list[RawItem]:
    """Only returns anything during a decision wave. Empty result is normal."""
    import httpx

    items: list[RawItem] = []
    for venue in source["venues"]:
        response = httpx.get(
            source["url"],
            params={"invitation": f"{venue}/-/Decision", "limit": 1000},
            follow_redirects=True,
            timeout=30,
        )
        response.raise_for_status()
        for note in response.json().get("notes", []):
            published_at = datetime.fromtimestamp(
                note["cdate"] / 1000, tz=timezone.utc
            )
            if not (since <= published_at < until):
                continue
            items.append(
                RawItem(
                    source_id=source["id"],
                    kind="paper",
                    title=note["content"]["title"]["value"],
                    url=f"https://openreview.net/forum?id={note['id']}",
                    published_at=published_at,
                )
            )
    return items


def fetch_github_advisories(source: dict, since: datetime, until: datetime) -> list[RawItem]:
    """GraphQL securityAdvisories(ecosystem: PIP|NPM). Needs GITHUB_TOKEN."""
    import os

    import httpx

    query = """
    query($ecosystem: SecurityAdvisoryEcosystem!, $since: DateTime!) {
      securityAdvisories(ecosystem: $ecosystem, first: 100, publishedSince: $since,
                          orderBy: {field: PUBLISHED_AT, direction: DESC}) {
        nodes { ghsaId summary publishedAt permalink identifiers { type value } }
      }
    }
    """
    token = os.environ["GITHUB_TOKEN"]
    items: list[RawItem] = []
    for ecosystem in ("PIP", "NPM"):
        response = httpx.post(
            source["url"],
            json={"query": query, "variables": {"ecosystem": ecosystem, "since": since.isoformat()}},
            headers={"Authorization": f"Bearer {token}"},
            follow_redirects=True,
            timeout=30,
        )
        response.raise_for_status()
        nodes = response.json()["data"]["securityAdvisories"]["nodes"]
        for node in nodes:
            published_at = datetime.fromisoformat(node["publishedAt"].replace("Z", "+00:00"))
            if not (since <= published_at < until):
                continue
            cve_ids = [i["value"] for i in node["identifiers"] if i["type"] == "CVE"]
            items.append(
                RawItem(
                    source_id=source["id"],
                    kind="advisory",
                    title=node["summary"],
                    url=node["permalink"],
                    published_at=published_at,
                    meta={"cve_ids": cve_ids} if cve_ids else {},
                )
            )
    return items


# One selector set per scraped source. Keep every source's selectors here so
# breakage from a site redesign is visible and repairable in one place.
SELECTORS: dict[str, dict[str, str]] = {
    "openai-blog": {
        "item": "article",
        "title": "h3",
        "link": "a",
        "date": "time",
    },
    "meta-ai-blog": {
        "item": "article",
        "title": "h3",
        "link": "a",
        "date": "time",
    },
    "mistral-news": {
        "item": "article",
        "title": "h2",
        "link": "a",
        "date": "time",
    },
    "anthropic-alignment": {
        "item": "article",
        "title": "h2",
        "link": "a",
        "date": "time",
    },
    "deepmind-safety": {
        "item": "article",
        "title": "h3",
        "link": "a",
        "date": "time",
    },
    "uk-aisi": {
        "item": "article",
        "title": "h3",
        "link": "a",
        "date": "time",
    },
}


def fetch_scrape(source: dict, since: datetime, until: datetime) -> list[RawItem]:
    """Last resort for lab blogs with no feed. httpx + selectolax.

    Keep one selector per source in a SELECTORS dict in fetch.py so breakage
    is visible and repairable in one place.
    """
    from urllib.parse import urljoin

    import httpx
    from selectolax.parser import HTMLParser

    selectors = SELECTORS[source["id"]]
    response = httpx.get(source["url"], timeout=30, follow_redirects=True)
    response.raise_for_status()
    tree = HTMLParser(response.text)

    items: list[RawItem] = []
    for node in tree.css(selectors["item"]):
        title_node = node.css_first(selectors["title"])
        link_node = node.css_first(selectors["link"])
        date_node = node.css_first(selectors["date"])
        if not (title_node and link_node and date_node):
            continue
        date_str = date_node.attributes.get("datetime") or date_node.text()
        try:
            published_at = datetime.fromisoformat(date_str.strip().replace("Z", "+00:00"))
        except ValueError:
            continue
        if not (since <= published_at < until):
            continue
        href = link_node.attributes.get("href", "")
        items.append(
            RawItem(
                source_id=source["id"],
                kind="article",
                title=title_node.text(strip=True),
                url=urljoin(source["url"], href),
                published_at=published_at,
            )
        )
    return items


FETCHERS = {
    "rss": fetch_rss,
    "arxiv": fetch_arxiv,
    "api": None,  # dispatch on source_id -> fetch_hf_daily / fetch_openreview / ...
    "scrape": fetch_scrape,
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--week", help="ISO week, e.g. 2026-W34. Defaults to last complete week.")
    parser.add_argument("--only", help="Comma-separated source ids, for debugging.")
    args = parser.parse_args()
    raise NotImplementedError


if __name__ == "__main__":
    main()
