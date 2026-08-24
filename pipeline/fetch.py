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
from datetime import datetime

from models import RawItem


def fetch_rss(source: dict, since: datetime, until: datetime) -> list[RawItem]:
    """feedparser. Fall back to <updated> when <published> is missing."""
    raise NotImplementedError


def fetch_arxiv(source: dict, since: datetime, until: datetime) -> list[RawItem]:
    """arXiv API: http://export.arxiv.org/api/query

    search_query=cat:cs.CL, sortBy=submittedDate, sortOrder=descending.
    Paginate 100 at a time until published_at < since.
    Rate limit: sleep 3s between calls. arXiv will block you otherwise.
    """
    raise NotImplementedError


def fetch_hf_daily(source: dict, since: datetime, until: datetime) -> list[RawItem]:
    """GET /api/daily_papers?date=YYYY-MM-DD per day in the window.

    Keep paper.upvotes and paper.id in meta — score.py needs both.
    """
    raise NotImplementedError


def fetch_openreview(source: dict, since: datetime, until: datetime) -> list[RawItem]:
    """Only returns anything during a decision wave. Empty result is normal."""
    raise NotImplementedError


def fetch_github_advisories(source: dict, since: datetime, until: datetime) -> list[RawItem]:
    """GraphQL securityAdvisories(ecosystem: PIP|NPM). Needs GITHUB_TOKEN."""
    raise NotImplementedError


def fetch_scrape(source: dict, since: datetime, until: datetime) -> list[RawItem]:
    """Last resort for lab blogs with no feed. httpx + selectolax.

    Keep one selector per source in a SELECTORS dict here so breakage is
    obvious and repairable in one place.
    """
    raise NotImplementedError


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
