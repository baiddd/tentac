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
import os
import sys
import time
from datetime import datetime, timedelta, timezone

from models import RawItem

# Some sites 403 the default python-httpx / python-requests user-agent
# string outright, independent of IP reputation (confirmed for science.org
# and Substack feeds). A realistic browser UA costs nothing and recovers
# those; it does NOT get past sites doing real bot-challenge/fingerprint
# checks (Cloudflare-style), which need a different approach entirely.
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
    )
}


def fetch_rss(source: dict, since: datetime, until: datetime) -> list[RawItem]:
    """feedparser. Fall back to <updated> when <published> is missing.

    A few sites (confirmed: cisa.gov) 403 httpx specifically — identical
    URL, identical headers, only the client library differs, and requests
    (a different but equally standard TLS stack) gets a clean 200. This is
    a TLS-handshake fingerprint quirk, not an active bot challenge, so
    retry once with requests on a 403 rather than failing the source.
    """
    import feedparser
    import httpx

    response = httpx.get(source["url"], follow_redirects=True, timeout=30, headers=_HEADERS)
    if response.status_code == 403:
        import requests

        response = requests.get(source["url"], timeout=30, headers=_HEADERS, allow_redirects=True)
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
        for attempt in range(3):
            try:
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
                    timeout=60,
                )
                break
            except httpx.TimeoutException:
                if attempt == 2:
                    raise
                time.sleep(5)
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
    """Only returns anything during a decision wave. Empty result is normal.

    Note: as of 2026-08, this endpoint returns a Cloudflare-style active
    challenge (403 ChallengeRequiredError) rather than serving results at
    all, independent of headers. That's a deliberate anti-bot barrier, not
    a stale-URL or UA problem — see the linked issue before attempting a
    "fix" here; it needs legitimate OpenReview API credentials, not a
    client-side workaround.
    """
    import httpx

    items: list[RawItem] = []
    for venue in source["venues"]:
        response = httpx.get(
            source["url"],
            params={"invitation": f"{venue}/-/Decision", "limit": 1000},
            follow_redirects=True,
            timeout=30,
            headers=_HEADERS,
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
    """GraphQL securityVulnerabilities(ecosystem: PIP|NPM). Needs GITHUB_TOKEN.

    The `securityAdvisories(ecosystem: ...)` query this originally called
    does not exist in GitHub's schema — `ecosystem` is only a valid
    argument on `securityVulnerabilities`, confirmed via introspection.
    That query has no publishedSince filter, only orderBy UPDATED_AT, so
    we paginate ordered by update time and stop once updated_at < since:
    published_at <= updated_at always holds, so nothing published in
    [since, until) can appear past that point. Each item is then kept
    only if its own published_at (not updated_at) falls in the window —
    an old advisory that was merely edited this week is correctly
    excluded, not reported as newly published.

    A single advisory can affect multiple packages, so the same GHSA ID
    can appear once per affected package within one ecosystem — dedupe
    on ghsaId across both ecosystem loops.
    """
    import os

    import httpx

    query = """
    query($ecosystem: SecurityAdvisoryEcosystem!, $after: String) {
      securityVulnerabilities(ecosystem: $ecosystem, first: 100, after: $after,
                               orderBy: {field: UPDATED_AT, direction: DESC}) {
        pageInfo { hasNextPage endCursor }
        nodes {
          updatedAt
          advisory { ghsaId summary publishedAt permalink identifiers { type value } }
        }
      }
    }
    """
    token = os.environ["GITHUB_TOKEN"]
    items: list[RawItem] = []
    seen_ghsa_ids: set[str] = set()
    for ecosystem in ("PIP", "NPM"):
        after = None
        while True:
            response = httpx.post(
                source["url"],
                json={"query": query, "variables": {"ecosystem": ecosystem, "after": after}},
                headers={"Authorization": f"Bearer {token}", **_HEADERS},
                follow_redirects=True,
                timeout=30,
            )
            response.raise_for_status()
            payload = response.json()
            if "errors" in payload:
                raise RuntimeError(f"GitHub GraphQL error for {source['id']}: {payload['errors']}")
            page = payload["data"]["securityVulnerabilities"]
            stop = False
            for node in page["nodes"]:
                updated_at = datetime.fromisoformat(node["updatedAt"].replace("Z", "+00:00"))
                if updated_at < since:
                    stop = True
                    break
                advisory = node["advisory"]
                if advisory["ghsaId"] in seen_ghsa_ids:
                    continue
                published_at = datetime.fromisoformat(advisory["publishedAt"].replace("Z", "+00:00"))
                if not (since <= published_at < until):
                    continue
                seen_ghsa_ids.add(advisory["ghsaId"])
                cve_ids = [i["value"] for i in advisory["identifiers"] if i["type"] == "CVE"]
                items.append(
                    RawItem(
                        source_id=source["id"],
                        kind="advisory",
                        title=advisory["summary"],
                        url=advisory["permalink"],
                        published_at=published_at,
                        meta={"cve_ids": cve_ids} if cve_ids else {},
                    )
                )
            if stop or not page["pageInfo"]["hasNextPage"]:
                break
            after = page["pageInfo"]["endCursor"]
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
    "anthropic-news": {
        # The page also renders a "Featured" hero grid with overlapping
        # articles in different markup (h2/h4 titles, no reliable class).
        # PublicationList is the plain reverse-chron list, covers every
        # recent post, and is what we want for weekly discovery.
        "item": "a[class*='PublicationList']",
        "title": "span[class*='title']",
        "link": "",
        "date": "time",
    },
    "uk-aisi": {
        "item": "article",
        "title": "h3",
        "link": "a",
        "date": "time",
    },
}


def _parse_scrape_date(date_str: str) -> datetime | None:
    """ISO first (most sites); fall back to "Mon D, YYYY" (e.g. anthropic.com's
    visible card dates, which carry no machine-readable datetime attribute).
    Date-only formats resolve to midnight UTC — fine for week-window filtering.
    """
    date_str = date_str.strip()
    try:
        return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
    except ValueError:
        pass
    try:
        return datetime.strptime(date_str, "%b %d, %Y").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def fetch_scrape(source: dict, since: datetime, until: datetime) -> list[RawItem]:
    """Last resort for lab blogs with no feed. httpx + selectolax.

    Keep one selector per source in a SELECTORS dict in fetch.py so breakage
    is visible and repairable in one place. An empty/missing "link" selector
    means the item node itself is the link (its own href is used) — some
    sites (anthropic.com/news) wrap the whole card in a single <a>, with no
    separate inner link to select.
    """
    from urllib.parse import urljoin

    import httpx
    from selectolax.parser import HTMLParser

    selectors = SELECTORS[source["id"]]
    response = httpx.get(source["url"], timeout=30, follow_redirects=True, headers=_HEADERS)
    response.raise_for_status()
    tree = HTMLParser(response.text)

    items: list[RawItem] = []
    for node in tree.css(selectors["item"]):
        title_node = node.css_first(selectors["title"])
        link_node = node if not selectors.get("link") else node.css_first(selectors["link"])
        date_node = node.css_first(selectors["date"])
        if not (title_node and link_node and date_node):
            continue
        date_str = date_node.attributes.get("datetime") or date_node.text()
        published_at = _parse_scrape_date(date_str)
        if published_at is None:
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


def _fetch_api(source: dict, since: datetime, until: datetime) -> list[RawItem]:
    dispatch = {
        "hf-daily-papers": fetch_hf_daily,
        "openreview": fetch_openreview,
        "github-advisories": fetch_github_advisories,
    }
    handler = dispatch.get(source["id"])
    if handler is None:
        raise NotImplementedError(f"no api fetcher registered for source {source['id']!r}")
    return handler(source, since, until)


FETCHERS = {
    "rss": fetch_rss,
    "arxiv": fetch_arxiv,
    "api": _fetch_api,
    "scrape": fetch_scrape,
}


def _load_sources(only: set[str] | None) -> list[dict]:
    import yaml

    with open("config/sources.yaml", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    sources = []
    for group in ("papers", "journals", "labs", "news", "security", "safety"):
        for source in config.get(group, []):
            if only is None or source["id"] in only:
                sources.append(source)
    return sources


def main() -> None:
    from dates import current_week, week_bounds, week_from_date

    parser = argparse.ArgumentParser()
    parser.add_argument("--week", help="ISO week, e.g. 2026-W34. Defaults to last complete week.")
    parser.add_argument(
        "--date",
        help="Any date within the target week, e.g. 2026-08-24 — an alternative to --week.",
    )
    parser.add_argument("--only", help="Comma-separated source ids, for debugging.")
    args = parser.parse_args()

    if args.week and args.date:
        parser.error("--week and --date are mutually exclusive")

    week = week_from_date(args.date) if args.date else (args.week or current_week())
    since, until = week_bounds(week)
    only = set(args.only.split(",")) if args.only else None

    sources = _load_sources(only)
    stats = {"sources_ok": 0, "sources_failed": 0, "items": 0}
    failures: list[tuple[str, str]] = []
    out_dir = "data/raw"
    os.makedirs(out_dir, exist_ok=True)
    out_path = f"{out_dir}/{week}.jsonl"

    with open(out_path, "w", encoding="utf-8") as out:
        for source in sources:
            fetcher = FETCHERS.get(source["kind"])
            if fetcher is None:
                reason = f"no fetcher for kind={source['kind']!r}"
                print(f"[{source['id']}] SKIPPED: {reason}")
                stats["sources_failed"] += 1
                failures.append((source["id"], reason))
                continue
            try:
                items = fetcher(source, since, until)
            except Exception as exc:  # noqa: BLE001 - one dead feed must never kill the run
                print(f"[{source['id']}] FAILED: {exc}")
                stats["sources_failed"] += 1
                failures.append((source["id"], str(exc)))
                continue
            for item in items:
                out.write(item.model_dump_json() + "\n")
            stats["items"] += len(items)
            stats["sources_ok"] += 1
            print(f"[{source['id']}] {len(items)} items")

    print(f"done: {stats}")
    if failures:
        print(f"\n=== {len(failures)} source(s) failed this run ===")
        for source_id, reason in failures:
            print(f"  - {source_id}: {reason}")
    else:
        print("\nall sources fetched successfully")


if __name__ == "__main__":
    main()
