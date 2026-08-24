# ai-weekly: pipeline + responsive site + GitHub deploy — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the `ai-weekly` scaffold into a working weekly AI digest — a Python pipeline (fetch → score → build) run by GitHub Actions, and a responsive, zero-client-JS Astro site published to GitHub Pages under the `tentac` GitHub repo — with every news item linking out to its clickable source(s), and an AI-generated 🤖 summary block per issue.

**Architecture:** Three CLI stages under `pipeline/` share a pydantic schema (`models.py`). `fetch.py` collects `RawItem`s per source into `data/raw/<week>.jsonl`. `score.py` dedupes, prefilters, calls Claude Sonnet 5 in batches of ~20 to classify+score, then ranks into `data/scored/<week>.jsonl`. `build.py` assembles the final `Issue`, writes `data/<week>.json` atomically, and updates `data/index.json` / `data/seen.json`. The Astro site under `web/` reads only committed JSON at build time (`import.meta.glob`) — no runtime fetch. Two GitHub Actions workflows (already scaffolded) run the pipeline on a Monday cron and deploy the site on every push to `data/` or `web/`.

**Tech Stack:** Python 3.12 (pydantic 2, httpx, feedparser, selectolax, rapidfuzz, tenacity, anthropic SDK), pytest + respx + freezegun for tests, Node 22 + Astro for the site, GitHub Actions + GitHub Pages, `gh` CLI for repo/Pages setup.

**Spec:** `PLAN.md` (repo root) — the original phase-by-phase design. This plan implements Phases 0–4; Phase 5 (email digest, per-section RSS, `notable` pin) is explicitly out of scope, per PLAN.md's own "worth having, once it runs" framing.

## Global Constraints

- `dedupe_key` preference order: DOI > arXiv ID > CVE ID > normalized URL (strip `utm_*` params, trailing slash, leading `www.`, and arXiv version suffix `v2`+).
- `week_bounds`: ISO weeks, UTC, half-open interval `[monday 00:00, next monday 00:00)`. Year-boundary case: `2026-W01` starts `2025-12-29`.
- arXiv rate limit: sleep 3 seconds between calls to `export.arxiv.org` — non-negotiable.
- Network retries: `tenacity`, 3 attempts, exponential backoff, on connection/timeout errors only (not on 4xx).
- HTTP cache: ETag / Last-Modified stored under `.cache/<source_id>.json`, sent as conditional headers on the next run.
- Near-dupe title matching: lowercase, strip punctuation, `rapidfuzz.fuzz.token_set_ratio >= 92`.
- Prefilter target: 400+ raw items → ~120 survive. Auto-keep: tier-1 sources, anything with a CVE id, HF upvotes ≥ 30. Drop: empty summary/abstract, arXiv revisions whose base id is already in `data/seen.json`.
- `classify_and_score`: one Claude call per ~20 items, strict JSON array out: `{"url","section","score","why"}`, `why` ≤ 20 words. Validate `section` against the `SectionId` literal; drop rows that fail validation instead of raising.
- Rank formula: `final = 0.55*model_score + 0.25*social + 0.20*source_tier`, `social` = log-normalized HF upvotes / GitHub stars, `source_tier` = `(4 - tier) / 3` (tier 1 → 1.0, tier 2 → 0.667, tier 3 → 0.333). Cap 6 items/section, 8 for `security` when any item that week carries a CVE (= "active incident").
- `write_headline`: one Claude call over the top ~10 items by rank, one sentence, no hype, no "X: Y" colon-subtitle construction. If nothing stands out, say the week was quiet.
- `build.py` writes `data/<week>.json` atomically: write to `data/.<week>.json.tmp`, then `os.replace` to the final path.
- LLM model: `claude-sonnet-5` for both `classify_and_score` and `write_headline` — chosen for cost (a few cents/week at this volume) over `claude-opus-5`; confirmed with the user given this is a budget-conscious hobby project.
- Astro: zero client JS by default. Read `data/*.json` at build time via `import.meta.glob` — no `fetch` at runtime, no loading states.
- Routes: `/` (latest issue), `/w/[week]` (a past issue), `/archive` (every issue, newest first), `/rss.xml` (self-feed).
- Design pass before CSS: pick a palette of 4–6 named hex values, a display face + body face chosen for this subject, one signature element. Avoid the current AI-default looks (cream+warm-clay, near-black+one-acid-accent, broadsheet hairline-rule grid).
- Every item card: `why` is the primary text (large), `title` is secondary (smaller) — reader scans a section in 10 seconds. Title text and any `mirrors` links are clickable `<a>` elements pointing at the source `url`(s), opening in a new tab (`target="_blank" rel="noopener"`).
- Each issue page shows a 🤖-prefixed callout block for the AI-generated `headline` field, visually distinct from the editorial `why` lines (so readers know it's model-generated).
- Quality floor: responsive down to a 360px mobile viewport, visible `:focus-visible` outline on every interactive element, `@media (prefers-reduced-motion: reduce)` disables non-essential transitions.
- GitHub repo: `tentac`, public, owned by the authenticated `gh` account (`baiddd`). Local git root is `D:\Projets\tentac\ai-weekly`.

---

## Task 1: Repo bootstrap — git, GitHub, Pages, dev tooling

**Files:**
- Create: `D:\Projets\tentac\ai-weekly\requirements-dev.txt`
- Create: `D:\Projets\tentac\ai-weekly\pytest.ini`
- Create: `D:\Projets\tentac\ai-weekly\.python-version`
- Modify: `D:\Projets\tentac\ai-weekly\.gitignore` (add `docs/superpowers/` is NOT ignored — plans/specs are committed; only add `.venv/`)

**Interfaces:**
- Produces: a `git` repo at `ai-weekly/` with remote `origin` pointing at `github.com/baiddd/tentac`, Pages enabled with source "GitHub Actions", and a working `pytest` invocation (even with zero tests collected) other tasks can add to.

- [ ] **Step 1: Add dev/test dependencies**

Create `requirements-dev.txt`:

```
-r requirements.txt
pytest>=8.0
pytest-asyncio>=0.24
respx>=0.21
freezegun>=1.5
```

- [ ] **Step 2: Pin the interpreter and add pytest config**

Create `.python-version`:

```
3.12
```

Create `pytest.ini`:

```ini
[pytest]
pythonpath = pipeline
testpaths = tests
asyncio_mode = auto
```

- [ ] **Step 3: Extend .gitignore**

Add one line to the existing `.gitignore`:

```
.venv/
```

- [ ] **Step 4: Create a virtualenv and install**

Run:
```bash
cd /d/Projets/tentac/ai-weekly
python -m venv .venv
.venv/Scripts/python -m pip install --upgrade pip
.venv/Scripts/python -m pip install -r requirements-dev.txt
```

If `selectolax` or `rapidfuzz` fail to build a wheel for the local Python version, retry with `--only-binary=:all:` and report the failure — do not silently fall back to a source build that might not have a compiler available. This is a known risk on very new Python versions; note it in the task's report but do not block the rest of the plan on it (fetch/score tests can still run against the other modules).

- [ ] **Step 5: Verify pytest runs (collects zero tests, exits 0)**

Run: `.venv/Scripts/python -m pytest`
Expected: `no tests ran` / exit code 0 (or 5, pytest's "no tests collected" code — either is fine at this point).

- [ ] **Step 6: git init and first commit**

```bash
cd /d/Projets/tentac/ai-weekly
git init
git add .
git commit -m "chore: scaffold ai-weekly (plan, config, pipeline stubs, workflows)"
```

- [ ] **Step 7: Create the GitHub repo and push**

```bash
gh repo create tentac --public --source=. --remote=origin --push
```

Verify: `git remote -v` shows `origin` pointing at `github.com/baiddd/tentac`.

- [ ] **Step 8: Enable GitHub Pages with source "GitHub Actions"**

```bash
gh api -X POST repos/baiddd/tentac/pages -f build_type=workflow
```

If it returns 409 (already enabled), that's fine — verify with `gh api repos/baiddd/tentac/pages` that `build_type` is `workflow`.

- [ ] **Step 9: Commit the dev tooling files**

```bash
git add requirements-dev.txt pytest.ini .python-version .gitignore
git commit -m "chore: add dev/test tooling"
git push
```

---

## Task 2: `pipeline/dates.py` — `week_bounds`

**Files:**
- Create: `pipeline/dates.py`
- Test: `tests/test_dates.py`

**Interfaces:**
- Produces: `week_bounds(week: str) -> tuple[datetime, datetime]` — both UTC-aware, `(monday_00_00, next_monday_00_00)`. Consumed by `fetch.py` (Task 10) and `build.py` (Task 17).
- Produces: `current_week() -> str` — returns the ISO week string (`"YYYY-Www"`) of the last complete week as of "now" (UTC). Consumed by `fetch.py` main() as the `--week` default.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_dates.py
from datetime import datetime, timezone

import pytest
from freezegun import freeze_time

from dates import week_bounds, current_week


def test_week_bounds_mid_year():
    start, end = week_bounds("2026-W34")
    assert start == datetime(2026, 8, 17, tzinfo=timezone.utc)
    assert end == datetime(2026, 8, 24, tzinfo=timezone.utc)


def test_week_bounds_year_boundary():
    start, end = week_bounds("2026-W01")
    assert start == datetime(2025, 12, 29, tzinfo=timezone.utc)
    assert end == datetime(2026, 1, 5, tzinfo=timezone.utc)


def test_week_bounds_rejects_bad_format():
    with pytest.raises(ValueError):
        week_bounds("2026-34")


@freeze_time("2026-08-24 10:00:00")  # a Monday
def test_current_week_on_monday_returns_prior_week():
    # Monday 06:00 UTC cron covers the week that just closed.
    assert current_week() == "2026-W34"


@freeze_time("2026-08-20 10:00:00")  # a Thursday, mid-week
def test_current_week_midweek_returns_prior_complete_week():
    assert current_week() == "2026-W33"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_dates.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'dates'`

- [ ] **Step 3: Implement `pipeline/dates.py`**

```python
"""ISO-week arithmetic, UTC throughout. Every pipeline stage uses this."""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

_WEEK_RE = re.compile(r"^(\d{4})-W(\d{2})$")


def week_bounds(week: str) -> tuple[datetime, datetime]:
    """Half-open UTC interval [monday 00:00, next monday 00:00) for an ISO week."""
    match = _WEEK_RE.match(week)
    if not match:
        raise ValueError(f"expected ISO week like '2026-W34', got {week!r}")
    year, week_num = int(match.group(1)), int(match.group(2))
    monday = datetime.fromisocalendar(year, week_num, 1).replace(tzinfo=timezone.utc)
    return monday, monday + timedelta(days=7)


def current_week() -> str:
    """ISO week string of the last complete week as of now (UTC)."""
    now = datetime.now(timezone.utc)
    last_complete_monday = now - timedelta(days=now.isoweekday())
    iso = last_complete_monday.isocalendar()
    return f"{iso.year}-W{iso.week:02d}"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_dates.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add pipeline/dates.py tests/test_dates.py
git commit -m "feat: implement week_bounds and current_week"
```

---

## Task 3: `pipeline/models.py` — `RawItem.dedupe_key`

**Files:**
- Modify: `pipeline/models.py:37-45`
- Test: `tests/test_models.py`

**Interfaces:**
- Consumes: nothing new — `RawItem` already exists.
- Produces: `RawItem.dedupe_key` property, `str`. Consumed by `score.dedupe` (Task 11).

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_models.py
from models import RawItem


def _item(**overrides) -> RawItem:
    base = dict(
        source_id="arxiv-cs-cl",
        kind="paper",
        title="A Paper",
        url="https://arxiv.org/abs/2508.01234v2",
        published_at="2026-08-18T00:00:00Z",
        meta={},
    )
    base.update(overrides)
    return RawItem(**base)


def test_dedupe_key_prefers_doi():
    item = _item(meta={"doi": "10.1038/s41586-026-00001-x", "arxiv_id": "2508.01234"})
    assert item.dedupe_key == "doi:10.1038/s41586-026-00001-x"


def test_dedupe_key_prefers_arxiv_over_url():
    item = _item(meta={"arxiv_id": "2508.01234v2"})
    assert item.dedupe_key == "arxiv:2508.01234"


def test_dedupe_key_prefers_cve_over_url():
    item = _item(
        url="https://example.com/blog/post",
        meta={"cve_ids": ["CVE-2026-12345"]},
    )
    assert item.dedupe_key == "cve:CVE-2026-12345"


def test_dedupe_key_normalizes_url_strips_utm_www_trailing_slash():
    item = _item(
        url="https://www.example.com/blog/post/?utm_source=x&utm_medium=y",
        meta={},
    )
    assert item.dedupe_key == "url:https://example.com/blog/post"


def test_dedupe_key_falls_back_to_url_when_no_ids():
    item = _item(url="https://example.com/a", meta={})
    assert item.dedupe_key == "url:https://example.com/a"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_models.py -v`
Expected: FAIL — `NotImplementedError`

- [ ] **Step 3: Implement `dedupe_key`**

Replace `pipeline/models.py:37-45` (the `dedupe_key` property body) with:

```python
    @property
    def dedupe_key(self) -> str:
        """Normalized identity. Prefer a stable ID over the URL.

        Order of preference: DOI > arXiv ID > CVE ID > normalized URL.
        The same paper shows up on arXiv, HF Daily Papers, and a lab blog;
        these must collapse into one item that keeps all three links.
        """
        if doi := self.meta.get("doi"):
            return f"doi:{doi}"
        if arxiv_id := self.meta.get("arxiv_id"):
            return f"arxiv:{_strip_arxiv_version(arxiv_id)}"
        if cve_ids := self.meta.get("cve_ids"):
            return f"cve:{cve_ids[0]}"
        return f"url:{_normalize_url(str(self.url))}"
```

Add the two helpers above the `RawItem` class (after the `ItemKind` definition, before `class RawItem`):

```python
import re
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

_ARXIV_VERSION_RE = re.compile(r"v\d+$")


def _strip_arxiv_version(arxiv_id: str) -> str:
    return _ARXIV_VERSION_RE.sub("", arxiv_id)


def _normalize_url(url: str) -> str:
    parts = urlsplit(url)
    netloc = parts.netloc[4:] if parts.netloc.startswith("www.") else parts.netloc
    query = urlencode(
        [(k, v) for k, v in parse_qsl(parts.query) if not k.startswith("utm_")]
    )
    path = parts.path.rstrip("/") or ""
    return urlunsplit((parts.scheme, netloc, path, query, ""))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_models.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add pipeline/models.py tests/test_models.py
git commit -m "feat: implement RawItem.dedupe_key"
```

---

## Task 4: `pipeline/fetch.py` — `fetch_rss`

**Files:**
- Modify: `pipeline/fetch.py:19-21`
- Test: `tests/test_fetch_rss.py`

**Interfaces:**
- Consumes: `RawItem` (Task 3's module).
- Produces: `fetch_rss(source: dict, since: datetime, until: datetime) -> list[RawItem]`. Consumed by `fetch.main` (Task 10) via `FETCHERS["rss"]`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_fetch_rss.py
from datetime import datetime, timezone

import respx
import httpx

from fetch import fetch_rss

FEED_XML = """<?xml version="1.0"?>
<rss version="2.0"><channel>
<title>Test Feed</title>
<item>
  <title>In window</title>
  <link>https://example.com/in-window</link>
  <pubDate>Tue, 18 Aug 2026 12:00:00 GMT</pubDate>
  <description>Summary A</description>
</item>
<item>
  <title>Out of window</title>
  <link>https://example.com/out-of-window</link>
  <pubDate>Tue, 11 Aug 2026 12:00:00 GMT</pubDate>
  <description>Summary B</description>
</item>
</channel></rss>
"""


@respx.mock
def test_fetch_rss_filters_to_window_and_maps_fields():
    respx.get("https://example.com/feed.xml").mock(
        return_value=httpx.Response(200, text=FEED_XML)
    )
    source = {"id": "example-blog", "url": "https://example.com/feed.xml"}
    since = datetime(2026, 8, 17, tzinfo=timezone.utc)
    until = datetime(2026, 8, 24, tzinfo=timezone.utc)

    items = fetch_rss(source, since, until)

    assert len(items) == 1
    item = items[0]
    assert item.source_id == "example-blog"
    assert item.kind == "article"
    assert item.title == "In window"
    assert str(item.url) == "https://example.com/in-window"
    assert item.summary == "Summary A"
    assert item.published_at == datetime(2026, 8, 18, 12, 0, tzinfo=timezone.utc)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/test_fetch_rss.py -v`
Expected: FAIL — `NotImplementedError`

- [ ] **Step 3: Implement `fetch_rss`**

Replace `pipeline/fetch.py:19-21` with:

```python
def fetch_rss(source: dict, since: datetime, until: datetime) -> list[RawItem]:
    """feedparser. Fall back to <updated> when <published> is missing."""
    import feedparser

    parsed = feedparser.parse(source["url"])
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
```

Add `from datetime import datetime, timezone` to the top-level imports (replacing the existing bare `from datetime import datetime`).

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python -m pytest tests/test_fetch_rss.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add pipeline/fetch.py tests/test_fetch_rss.py
git commit -m "feat: implement fetch_rss"
```

---

## Task 5: `pipeline/fetch.py` — `fetch_arxiv`

**Files:**
- Modify: `pipeline/fetch.py` (the `fetch_arxiv` stub)
- Test: `tests/test_fetch_arxiv.py`

**Interfaces:**
- Produces: `fetch_arxiv(source: dict, since: datetime, until: datetime) -> list[RawItem]`, called by `fetch.main` via `FETCHERS["arxiv"]`. Sets `meta["arxiv_id"]` for `dedupe_key`. Sleeps 3s between paginated calls (mockable via monkeypatching `time.sleep`).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_fetch_arxiv.py
from datetime import datetime, timezone
from unittest.mock import patch

import respx
import httpx

from fetch import fetch_arxiv

ATOM_PAGE_1 = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
<entry>
  <id>http://arxiv.org/abs/2508.01234v2</id>
  <title>In window paper</title>
  <summary>Abstract text</summary>
  <published>2026-08-18T00:00:00Z</published>
  <author><name>Jane Doe</name></author>
</entry>
<entry>
  <id>http://arxiv.org/abs/2508.00001v1</id>
  <title>Out of window paper</title>
  <summary>Abstract text 2</summary>
  <published>2026-08-10T00:00:00Z</published>
  <author><name>John Roe</name></author>
</entry>
</feed>
"""


@respx.mock
@patch("fetch.time.sleep")
def test_fetch_arxiv_maps_fields_and_stops_before_since(mock_sleep):
    respx.get("http://export.arxiv.org/api/query").mock(
        return_value=httpx.Response(200, text=ATOM_PAGE_1)
    )
    source = {"id": "arxiv-cs-cl", "category": "cs.CL"}
    since = datetime(2026, 8, 17, tzinfo=timezone.utc)
    until = datetime(2026, 8, 24, tzinfo=timezone.utc)

    items = fetch_arxiv(source, since, until)

    assert len(items) == 1
    item = items[0]
    assert item.source_id == "arxiv-cs-cl"
    assert item.kind == "paper"
    assert item.title == "In window paper"
    assert item.meta["arxiv_id"] == "2508.01234v2"
    assert item.authors == ["Jane Doe"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/test_fetch_arxiv.py -v`
Expected: FAIL — `NotImplementedError`

- [ ] **Step 3: Implement `fetch_arxiv`**

Replace the `fetch_arxiv` stub with:

```python
def fetch_arxiv(source: dict, since: datetime, until: datetime) -> list[RawItem]:
    """arXiv API: http://export.arxiv.org/api/query

    search_query=cat:cs.CL, sortBy=submittedDate, sortOrder=descending.
    Paginate 100 at a time until published_at < since.
    Rate limit: sleep 3 seconds between calls, non-negotiable.
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
```

Add `import time` to the top-level imports of `pipeline/fetch.py`.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python -m pytest tests/test_fetch_arxiv.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add pipeline/fetch.py tests/test_fetch_arxiv.py
git commit -m "feat: implement fetch_arxiv with rate limiting"
```

---

## Task 6: `pipeline/fetch.py` — `fetch_hf_daily`

**Files:**
- Modify: `pipeline/fetch.py` (the `fetch_hf_daily` stub)
- Test: `tests/test_fetch_hf_daily.py`

**Interfaces:**
- Produces: `fetch_hf_daily(source: dict, since: datetime, until: datetime) -> list[RawItem]`, dispatched by `source_id` from `fetch.main` (Task 10). Sets `meta["hf_upvotes"]` and `meta["arxiv_id"]` when present — `score.prefilter` (Task 12) and `score.rank` (Task 14) read `hf_upvotes`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_fetch_hf_daily.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/test_fetch_hf_daily.py -v`
Expected: FAIL — `NotImplementedError`

- [ ] **Step 3: Implement `fetch_hf_daily`**

```python
def fetch_hf_daily(source: dict, since: datetime, until: datetime) -> list[RawItem]:
    """GET /api/daily_papers?date=YYYY-MM-DD per day in the window.

    Keep paper.upvotes and paper.id in meta — score.py needs both.
    """
    import httpx

    items: list[RawItem] = []
    day = since
    while day < until:
        response = httpx.get(
            source["url"], params={"date": day.strftime("%Y-%m-%d")}, timeout=30
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
```

Add `from datetime import timedelta` to `pipeline/fetch.py`'s imports (extend the existing `from datetime import datetime, timezone` line).

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python -m pytest tests/test_fetch_hf_daily.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add pipeline/fetch.py tests/test_fetch_hf_daily.py
git commit -m "feat: implement fetch_hf_daily"
```

---

## Task 7: `pipeline/fetch.py` — `fetch_openreview` and `fetch_github_advisories`

**Files:**
- Modify: `pipeline/fetch.py` (both stubs)
- Test: `tests/test_fetch_openreview.py`, `tests/test_fetch_github_advisories.py`

**Interfaces:**
- Produces: `fetch_openreview(source, since, until) -> list[RawItem]` — empty list is a normal, valid result (no assertion of non-emptiness anywhere downstream).
- Produces: `fetch_github_advisories(source, since, until) -> list[RawItem]` — sets `meta["cve_ids"]` when the advisory has CVE identifiers, used by `dedupe_key` (Task 3) and `score.prefilter`'s auto-keep rule (Task 12).

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_fetch_openreview.py
from datetime import datetime, timezone

import respx
import httpx

from fetch import fetch_openreview


@respx.mock
def test_fetch_openreview_empty_is_normal():
    respx.get("https://api2.openreview.net/notes").mock(
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
    respx.get("https://api2.openreview.net/notes").mock(
        return_value=httpx.Response(
            200,
            json={
                "notes": [
                    {
                        "id": "abc123",
                        "content": {"title": {"value": "Accepted Paper"}},
                        "cdate": 1755561600000,  # 2026-08-19T00:00:00Z in ms
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
```

```python
# tests/test_fetch_github_advisories.py
from datetime import datetime, timezone

import respx
import httpx

from fetch import fetch_github_advisories

GRAPHQL_RESPONSE = {
    "data": {
        "securityAdvisories": {
            "nodes": [
                {
                    "ghsaId": "GHSA-xxxx-yyyy-zzzz",
                    "summary": "Malicious package",
                    "publishedAt": "2026-08-18T00:00:00Z",
                    "permalink": "https://github.com/advisories/GHSA-xxxx-yyyy-zzzz",
                    "identifiers": [{"type": "CVE", "value": "CVE-2026-99999"}],
                }
            ]
        }
    }
}


@respx.mock
def test_fetch_github_advisories_sets_cve_ids(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "test-token")
    respx.post("https://api.github.com/graphql").mock(
        return_value=httpx.Response(200, json=GRAPHQL_RESPONSE)
    )
    source = {"id": "github-advisories", "url": "https://api.github.com/graphql"}
    since = datetime(2026, 8, 17, tzinfo=timezone.utc)
    until = datetime(2026, 8, 24, tzinfo=timezone.utc)

    items = fetch_github_advisories(source, since, until)
    assert len(items) == 1
    assert items[0].kind == "advisory"
    assert items[0].meta["cve_ids"] == ["CVE-2026-99999"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_fetch_openreview.py tests/test_fetch_github_advisories.py -v`
Expected: FAIL — `NotImplementedError`

- [ ] **Step 3: Implement both fetchers**

```python
def fetch_openreview(source: dict, since: datetime, until: datetime) -> list[RawItem]:
    """Only returns anything during a decision wave. Empty result is normal."""
    import httpx

    items: list[RawItem] = []
    for venue in source["venues"]:
        response = httpx.get(
            source["url"],
            params={"invitation": f"{venue}/-/Decision", "limit": 1000},
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_fetch_openreview.py tests/test_fetch_github_advisories.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add pipeline/fetch.py tests/test_fetch_openreview.py tests/test_fetch_github_advisories.py
git commit -m "feat: implement fetch_openreview and fetch_github_advisories"
```

---

## Task 8: `pipeline/fetch.py` — `fetch_scrape` + `SELECTORS`

**Files:**
- Modify: `pipeline/fetch.py` (the `fetch_scrape` stub)
- Test: `tests/test_fetch_scrape.py`

**Interfaces:**
- Produces: `fetch_scrape(source: dict, since: datetime, until: datetime) -> list[RawItem]` and a module-level `SELECTORS: dict[str, dict[str, str]]` keyed by `source_id`, each value holding CSS selectors `item`, `title`, `link`, `date` (optional `summary`).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_fetch_scrape.py
from datetime import datetime, timezone

import respx
import httpx

from fetch import fetch_scrape, SELECTORS

SAMPLE_HTML = """
<html><body>
<article class="post-card">
  <h2 class="post-title"><a href="/news/one">In window post</a></h2>
  <time datetime="2026-08-18T00:00:00Z"></time>
</article>
<article class="post-card">
  <h2 class="post-title"><a href="/news/two">Out of window post</a></h2>
  <time datetime="2026-08-01T00:00:00Z"></time>
</article>
</body></html>
"""


@respx.mock
def test_fetch_scrape_uses_registered_selector():
    SELECTORS["example-lab"] = {
        "item": "article.post-card",
        "title": "h2.post-title a",
        "link": "h2.post-title a",
        "date": "time",
    }
    respx.get("https://example.com/blog/").mock(
        return_value=httpx.Response(200, text=SAMPLE_HTML)
    )
    source = {"id": "example-lab", "url": "https://example.com/blog/"}
    since = datetime(2026, 8, 17, tzinfo=timezone.utc)
    until = datetime(2026, 8, 24, tzinfo=timezone.utc)

    items = fetch_scrape(source, since, until)

    assert len(items) == 1
    assert items[0].title == "In window post"
    assert str(items[0].url) == "https://example.com/news/one"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/test_fetch_scrape.py -v`
Expected: FAIL — `NotImplementedError` (and `SELECTORS` not yet defined)

- [ ] **Step 3: Implement `fetch_scrape` and `SELECTORS`**

Add above `fetch_scrape`:

```python
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
```

Replace the `fetch_scrape` stub with:

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python -m pytest tests/test_fetch_scrape.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add pipeline/fetch.py tests/test_fetch_scrape.py
git commit -m "feat: implement fetch_scrape with per-source SELECTORS"
```

---

## Task 9: `pipeline/fetch.py` — orchestration (`main`, caching, retries, per-source isolation)

**Files:**
- Modify: `pipeline/fetch.py` (the `FETCHERS["api"]` dispatch and `main`)
- Test: `tests/test_fetch_main.py`

**Interfaces:**
- Consumes: every `fetch_*` function from Tasks 4–8, `week_bounds`/`current_week` from Task 2, `config/sources.yaml`.
- Produces: `data/raw/<week>.jsonl` (one JSON object per line, `RawItem.model_dump(mode="json")`), `.cache/<source_id>.json` (ETag/Last-Modified — best-effort, only meaningfully used by `fetch_rss`), and run stats printed to stdout. One dead source must never abort the run.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_fetch_main.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/test_fetch_main.py -v`
Expected: FAIL — `NotImplementedError`

- [ ] **Step 3: Implement the dispatch table and `main`**

Replace the `FETCHERS` dict and `main` function at the bottom of `pipeline/fetch.py`:

```python
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

    with open("config/sources.yaml") as f:
        config = yaml.safe_load(f)
    sources = []
    for group in ("papers", "journals", "labs", "news", "security", "safety"):
        for source in config.get(group, []):
            if only is None or source["id"] in only:
                sources.append(source)
    return sources


def main() -> None:
    from dates import current_week, week_bounds

    parser = argparse.ArgumentParser()
    parser.add_argument("--week", help="ISO week, e.g. 2026-W34. Defaults to last complete week.")
    parser.add_argument("--only", help="Comma-separated source ids, for debugging.")
    args = parser.parse_args()

    week = args.week or current_week()
    since, until = week_bounds(week)
    only = set(args.only.split(",")) if args.only else None

    sources = _load_sources(only)
    stats = {"sources_ok": 0, "sources_failed": 0, "items": 0}
    out_dir = "data/raw"
    os.makedirs(out_dir, exist_ok=True)
    out_path = f"{out_dir}/{week}.jsonl"

    with open(out_path, "w") as out:
        for source in sources:
            fetcher = FETCHERS.get(source["kind"])
            if fetcher is None:
                print(f"[{source['id']}] no fetcher for kind={source['kind']!r}, skipping")
                stats["sources_failed"] += 1
                continue
            try:
                items = fetcher(source, since, until)
            except Exception as exc:  # noqa: BLE001 - one dead feed must never kill the run
                print(f"[{source['id']}] FAILED: {exc}")
                stats["sources_failed"] += 1
                continue
            for item in items:
                out.write(item.model_dump_json() + "\n")
            stats["items"] += len(items)
            stats["sources_ok"] += 1
            print(f"[{source['id']}] {len(items)} items")

    print(f"done: {stats}")


if __name__ == "__main__":
    main()
```

Add `import os` and `import sys` to the top of `pipeline/fetch.py` (`sys` is needed so the test can monkeypatch `fetch.sys.argv`; `argparse` already reads `sys.argv` by default, which works the same way).

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python -m pytest tests/test_fetch_main.py -v`
Expected: PASS

- [ ] **Step 5: Run the full fetch test suite**

Run: `.venv/Scripts/python -m pytest tests/test_fetch_rss.py tests/test_fetch_arxiv.py tests/test_fetch_hf_daily.py tests/test_fetch_openreview.py tests/test_fetch_github_advisories.py tests/test_fetch_scrape.py tests/test_fetch_main.py -v`
Expected: all PASS

- [ ] **Step 6: Commit**

```bash
git add pipeline/fetch.py tests/test_fetch_main.py
git commit -m "feat: implement fetch.py orchestration with per-source isolation"
```

*(Retry/backoff and ETag caching are intentionally minimal here — `tenacity` wraps `httpx.get` calls only where Task-level tests demand it. If a later manual run against real feeds shows retries are needed, add `@tenacity.retry(stop=stop_after_attempt(3), wait=wait_exponential(), retry=retry_if_exception_type((httpx.ConnectError, httpx.TimeoutException)))` to `fetch_rss`, `fetch_arxiv`, `fetch_hf_daily`, and `fetch_scrape` without changing their tested behavior — network errors keep raising, they just retry first.)*

---

## Task 10: `pipeline/score.py` — `dedupe`

**Files:**
- Modify: `pipeline/score.py` (the `dedupe` stub)
- Test: `tests/test_score_dedupe.py`

**Interfaces:**
- Consumes: `RawItem`, `RawItem.dedupe_key` (Task 3).
- Produces: `dedupe(items: list[RawItem]) -> list[RawItem]` — returns the highest-tier survivor per identity group; each survivor's `meta["mirror_urls"]` (new key, `list[str]`) holds the other groups' URLs, later copied into `ScoredItem.mirrors` by `classify_and_score` (Task 13).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_score_dedupe.py
from models import RawItem
from score import dedupe


def _item(source_id, url, title="Same Paper", **meta):
    return RawItem(
        source_id=source_id,
        kind="paper",
        title=title,
        url=url,
        published_at="2026-08-18T00:00:00Z",
        meta=meta,
    )


def test_dedupe_collapses_exact_key_keeps_highest_tier_source(monkeypatch):
    tiers = {"hf-daily-papers": 1, "arxiv-cs-cl": 2}
    monkeypatch.setattr("score.SOURCE_TIERS", tiers)

    items = [
        _item("arxiv-cs-cl", "https://arxiv.org/abs/2508.01234", arxiv_id="2508.01234"),
        _item("hf-daily-papers", "https://huggingface.co/papers/2508.01234", arxiv_id="2508.01234"),
    ]
    result = dedupe(items)

    assert len(result) == 1
    assert result[0].source_id == "hf-daily-papers"
    assert result[0].meta["mirror_urls"] == ["https://arxiv.org/abs/2508.01234"]


def test_dedupe_collapses_near_dupe_titles(monkeypatch):
    monkeypatch.setattr("score.SOURCE_TIERS", {"lab-blog": 1, "news-site": 3})
    items = [
        _item("lab-blog", "https://lab.com/a", title="New Model Beats Benchmark Records"),
        _item("news-site", "https://news.com/a", title="new model beats benchmark records!"),
    ]
    result = dedupe(items)
    assert len(result) == 1
    assert result[0].source_id == "lab-blog"


def test_dedupe_keeps_distinct_items():
    items = [_item("s1", "https://a.com/1", title="A"), _item("s2", "https://a.com/2", title="B")]
    result = dedupe(items)
    assert len(result) == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/test_score_dedupe.py -v`
Expected: FAIL — `NotImplementedError`

- [ ] **Step 3: Implement `dedupe`**

Add near the top of `pipeline/score.py` (module-level, populated by `main` from `sources.yaml`; defaulted here so unit tests can monkeypatch it and standalone calls don't crash):

```python
SOURCE_TIERS: dict[str, int] = {}


def _tier(source_id: str) -> int:
    return SOURCE_TIERS.get(source_id, 3)
```

Replace the `dedupe` stub:

```python
def dedupe(items: list[RawItem]) -> list[RawItem]:
    """Collapse on dedupe_key, then near-dupe titles.

    Title matching: lowercase, strip punctuation, compare with rapidfuzz
    token_set_ratio >= 92. Keep the item from the highest-tier source and
    push the rest into mirrors.
    """
    import re

    from rapidfuzz import fuzz

    groups: list[list[RawItem]] = []
    key_to_group: dict[str, int] = {}

    for item in items:
        key = item.dedupe_key
        if key in key_to_group:
            groups[key_to_group[key]].append(item)
            continue

        normalized_title = re.sub(r"[^\w\s]", "", item.title.lower())
        matched_group = None
        for idx, group in enumerate(groups):
            group_title = re.sub(r"[^\w\s]", "", group[0].title.lower())
            if fuzz.token_set_ratio(normalized_title, group_title) >= 92:
                matched_group = idx
                break

        if matched_group is not None:
            groups[matched_group].append(item)
        else:
            key_to_group[key] = len(groups)
            groups.append([item])

    survivors: list[RawItem] = []
    for group in groups:
        group.sort(key=lambda i: _tier(i.source_id))
        winner = group[0]
        mirrors = [str(i.url) for i in group[1:]]
        if mirrors:
            winner = winner.model_copy(
                update={"meta": {**winner.meta, "mirror_urls": mirrors}}
            )
        survivors.append(winner)
    return survivors
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python -m pytest tests/test_score_dedupe.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add pipeline/score.py tests/test_score_dedupe.py
git commit -m "feat: implement score.dedupe"
```

---

## Task 11: `pipeline/score.py` — `prefilter`

**Files:**
- Modify: `pipeline/score.py` (the `prefilter` stub)
- Test: `tests/test_score_prefilter.py`

**Interfaces:**
- Consumes: `SOURCE_TIERS` / `_tier` (Task 10), `data/seen.json` (read-only here — a `set[str]` of `dedupe_key`s from prior issues).
- Produces: `prefilter(items: list[RawItem]) -> list[RawItem]`, called by `main` (Task 15) before `classify_and_score`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_score_prefilter.py
from models import RawItem
from score import prefilter


def _item(source_id, title, summary="An abstract.", **meta):
    return RawItem(
        source_id=source_id,
        kind="paper",
        title=title,
        url=f"https://example.com/{title.replace(' ', '-')}",
        published_at="2026-08-18T00:00:00Z",
        summary=summary,
        meta=meta,
    )


def test_prefilter_drops_empty_summary(monkeypatch):
    monkeypatch.setattr("score.SOURCE_TIERS", {"s": 2})
    monkeypatch.setattr("score._load_seen", lambda: set())
    items = [_item("s", "No abstract", summary="")]
    assert prefilter(items) == []


def test_prefilter_auto_keeps_tier1_even_without_summary(monkeypatch):
    monkeypatch.setattr("score.SOURCE_TIERS", {"tier1-src": 1})
    monkeypatch.setattr("score._load_seen", lambda: set())
    items = [_item("tier1-src", "Tier 1 item", summary="")]
    assert len(prefilter(items)) == 1


def test_prefilter_auto_keeps_cve_items(monkeypatch):
    monkeypatch.setattr("score.SOURCE_TIERS", {"s": 3})
    monkeypatch.setattr("score._load_seen", lambda: set())
    items = [_item("s", "Vuln", summary="", cve_ids=["CVE-2026-1"])]
    assert len(prefilter(items)) == 1


def test_prefilter_auto_keeps_high_hf_upvotes(monkeypatch):
    monkeypatch.setattr("score.SOURCE_TIERS", {"s": 3})
    monkeypatch.setattr("score._load_seen", lambda: set())
    items = [_item("s", "Popular", summary="", hf_upvotes=31)]
    assert len(prefilter(items)) == 1


def test_prefilter_drops_already_seen_arxiv_revision(monkeypatch):
    monkeypatch.setattr("score.SOURCE_TIERS", {"s": 2})
    monkeypatch.setattr("score._load_seen", lambda: {"arxiv:2508.01234"})
    items = [_item("s", "Revised paper", arxiv_id="2508.01234v3")]
    assert prefilter(items) == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/test_score_prefilter.py -v`
Expected: FAIL — `NotImplementedError`

- [ ] **Step 3: Implement `prefilter`**

Add a loader helper near `SOURCE_TIERS`:

```python
def _load_seen() -> set[str]:
    import json
    import os

    if not os.path.exists("data/seen.json"):
        return set()
    with open("data/seen.json") as f:
        return set(json.load(f))
```

Replace the `prefilter` stub:

```python
def prefilter(items: list[RawItem]) -> list[RawItem]:
    """Cheap cuts before spending any tokens. Target: 400+ -> ~120 items.

    Drop: no abstract, pure survey/benchmark-rehash titles, v2+ arXiv
    revisions already published in a prior issue (check data/seen.json).
    Auto-keep: tier 1 sources, anything with a CVE, HF upvotes >= 30.
    """
    seen = _load_seen()
    kept: list[RawItem] = []
    for item in items:
        if item.dedupe_key in seen:
            continue
        if _tier(item.source_id) == 1:
            kept.append(item)
            continue
        if item.meta.get("cve_ids"):
            kept.append(item)
            continue
        if item.meta.get("hf_upvotes", 0) >= 30:
            kept.append(item)
            continue
        if not item.summary.strip():
            continue
        kept.append(item)
    return kept
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python -m pytest tests/test_score_prefilter.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add pipeline/score.py tests/test_score_prefilter.py
git commit -m "feat: implement score.prefilter"
```

---

## Task 12: `pipeline/score.py` — `classify_and_score`

**Files:**
- Modify: `pipeline/score.py` (the `classify_and_score` stub)
- Test: `tests/test_score_classify.py`

**Interfaces:**
- Consumes: `RawItem`, `ScoredItem`, `SectionId` (`models.py`).
- Produces: `classify_and_score(items: list[RawItem]) -> list[ScoredItem]`, called by `main` (Task 15). Uses `anthropic.Anthropic().messages.create(model="claude-sonnet-5", ...)`, batched ~20 items/call. `mirrors` on the returned `ScoredItem` is populated from `RawItem.meta["mirror_urls"]` (set by `dedupe`, Task 10).

- [ ] **Step 1: Write the failing test**

Mock the Anthropic client — do not call the real API in tests.

```python
# tests/test_score_classify.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/test_score_classify.py -v`
Expected: FAIL — `NotImplementedError`

- [ ] **Step 3: Implement `classify_and_score`**

Add `from anthropic import Anthropic` and `from typing import get_args` to the top of `pipeline/score.py`, alongside the existing `from models import RawItem, ScoredItem` (extend to also import `SectionId`).

Replace the `classify_and_score` stub:

```python
_SCORE_PROMPT = """You are scoring items for a weekly AI digest read by working \
practitioners. For each item below, decide:

- section: exactly one of {sections}
- score: 0.0-1.0, "would a working practitioner regret missing this" — not \
"is this well written"
- why: <=20 words, the editorial line the reader sees. State what changed, \
no hedging, no "this paper proposes" framing. Security vs safety: an \
exploited vulnerability or a live incident is security; an eval, a policy, \
or interpretability work is safety.

Return a JSON array only, no prose, one object per item:
[{{"url": "...", "section": "...", "score": 0.0, "why": "..."}}, ...]

Items:
{items}
"""


def classify_and_score(items: list[RawItem]) -> list[ScoredItem]:
    """One batched LLM call per ~20 items. Ask for strict JSON:

        {"url": ..., "section": <SectionId>, "score": 0..1, "why": "<=20 words"}

    Validate every returned section against SectionId and drop malformed
    rows rather than trusting the model's output shape.
    """
    import json

    valid_sections = set(get_args(SectionId))
    by_url = {str(item.url): item for item in items}
    client = Anthropic()
    results: list[ScoredItem] = []

    batch_size = 20
    for start in range(0, len(items), batch_size):
        batch = items[start : start + batch_size]
        if not batch:
            continue
        items_text = "\n".join(
            f"- url: {item.url}\n  title: {item.title}\n  summary: {item.summary[:500]}"
            for item in batch
        )
        prompt = _SCORE_PROMPT.format(sections=sorted(valid_sections), items=items_text)
        response = client.messages.create(
            model="claude-sonnet-5",
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        )
        text = "".join(block.text for block in response.content if block.type == "text")
        try:
            rows = json.loads(text)
        except json.JSONDecodeError:
            continue

        for row in rows:
            url = row.get("url")
            source_item = by_url.get(url)
            if source_item is None:
                continue
            if row.get("section") not in valid_sections:
                continue
            score = row.get("score")
            if not isinstance(score, (int, float)) or not (0 <= score <= 1):
                continue
            why = row.get("why")
            if not why:
                continue

            mirror_urls = source_item.meta.get("mirror_urls", [])
            results.append(
                ScoredItem(
                    **source_item.model_dump(exclude={"meta"}),
                    meta=source_item.meta,
                    section=row["section"],
                    score=float(score),
                    why=why,
                    mirrors=mirror_urls,
                )
            )
    return results
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python -m pytest tests/test_score_classify.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add pipeline/score.py tests/test_score_classify.py
git commit -m "feat: implement score.classify_and_score against Claude Sonnet 5"
```

---

## Task 13: `pipeline/score.py` — `rank`

**Files:**
- Modify: `pipeline/score.py` (the `rank` stub)
- Test: `tests/test_score_rank.py`

**Interfaces:**
- Consumes: `ScoredItem`, `_tier` (Task 10).
- Produces: `rank(items: list[ScoredItem]) -> list[ScoredItem]`, called by `main` (Task 15) as the last stage before writing `data/scored/<week>.jsonl`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_score_rank.py
from models import ScoredItem
from score import rank


def _scored(section, score, source_id="s", **meta):
    return ScoredItem(
        source_id=source_id,
        kind="paper",
        title=f"Item {score}",
        url=f"https://example.com/{section}-{score}-{source_id}",
        published_at="2026-08-18T00:00:00Z",
        section=section,
        score=score,
        why="why",
        meta=meta,
    )


def test_rank_caps_six_per_section(monkeypatch):
    monkeypatch.setattr("score.SOURCE_TIERS", {"s": 2})
    items = [_scored("llm", 0.9 - i * 0.01) for i in range(10)]
    result = rank(items)
    assert len(result) == 6


def test_rank_caps_eight_for_security_with_active_incident(monkeypatch):
    monkeypatch.setattr("score.SOURCE_TIERS", {"s": 2})
    items = [_scored("security", 0.9 - i * 0.01, cve_ids=["CVE-2026-1"]) for i in range(10)]
    result = rank(items)
    assert len(result) == 8


def test_rank_orders_by_blended_score_descending(monkeypatch):
    monkeypatch.setattr("score.SOURCE_TIERS", {"tier1": 1, "tier3": 3})
    low_score_tier1 = _scored("llm", 0.5, source_id="tier1")
    high_score_tier3 = _scored("llm", 0.9, source_id="tier3")
    result = rank([high_score_tier3, low_score_tier1])
    # source_tier component should pull tier-1 above a much higher raw score
    # only when scores are close; here 0.9 vs 0.5 model_score dominates.
    assert result[0].score == 0.9


def test_rank_empty_section_returns_empty_list(monkeypatch):
    monkeypatch.setattr("score.SOURCE_TIERS", {"s": 2})
    assert rank([]) == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/test_score_rank.py -v`
Expected: FAIL — `NotImplementedError`

- [ ] **Step 3: Implement `rank`**

Replace the `rank` stub:

```python
def rank(items: list[ScoredItem]) -> list[ScoredItem]:
    """Blend the model score with hard signals, then cap per section.

        final = 0.55 * model_score
              + 0.25 * social      (log-normalized HF upvotes, GitHub stars)
              + 0.20 * source_tier

    Cap at 6 items per section, 8 for security during an active incident.
    A section with 0 items renders as "quiet week" — do not pad it.
    """
    import math
    from collections import defaultdict

    def social_component(item: ScoredItem) -> float:
        raw = item.meta.get("hf_upvotes") or item.meta.get("github_stars") or 0
        return min(math.log1p(raw) / math.log1p(1000), 1.0)

    def source_tier_component(item: ScoredItem) -> float:
        return (4 - _tier(item.source_id)) / 3

    def final_score(item: ScoredItem) -> float:
        return (
            0.55 * item.score
            + 0.25 * social_component(item)
            + 0.20 * source_tier_component(item)
        )

    by_section: dict[str, list[ScoredItem]] = defaultdict(list)
    for item in items:
        by_section[item.section].append(item)

    ranked: list[ScoredItem] = []
    for section, section_items in by_section.items():
        active_incident = section == "security" and any(
            i.meta.get("cve_ids") for i in section_items
        )
        cap = 8 if active_incident else 6
        section_items.sort(key=final_score, reverse=True)
        ranked.extend(section_items[:cap])
    return ranked
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python -m pytest tests/test_score_rank.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add pipeline/score.py tests/test_score_rank.py
git commit -m "feat: implement score.rank"
```

---

## Task 14: `pipeline/score.py` — `main` orchestration

**Files:**
- Modify: `pipeline/score.py` (add `main`, `argparse`, module docstring imports)
- Test: `tests/test_score_main.py`

**Interfaces:**
- Consumes: `dedupe`, `prefilter`, `classify_and_score`, `rank` (Tasks 10–13), `week_bounds`-independent (score just reads/writes by week string).
- Produces: `data/scored/<week>.jsonl`, populates `SOURCE_TIERS` from `config/sources.yaml` before running the pipeline. CLI: `python pipeline/score.py --week 2026-W34`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_score_main.py
import json
from unittest.mock import patch

import score


def test_main_reads_raw_writes_scored(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "sources.yaml").write_text(
        "papers:\n  - id: s\n    kind: rss\n    tier: 1\n    sections: [llm]\n"
    )
    (tmp_path / "data" / "raw").mkdir(parents=True)
    raw_item = {
        "source_id": "s",
        "kind": "paper",
        "title": "A Paper",
        "url": "https://example.com/a",
        "published_at": "2026-08-18T00:00:00Z",
        "summary": "Abstract",
        "authors": [],
        "meta": {},
    }
    (tmp_path / "data" / "raw" / "2026-W34.jsonl").write_text(json.dumps(raw_item) + "\n")

    with patch("score.classify_and_score") as mock_classify:
        from models import ScoredItem

        mock_classify.return_value = [
            ScoredItem(**raw_item, section="llm", score=0.9, why="why")
        ]
        monkeypatch.setattr("sys.argv", ["score.py", "--week", "2026-W34"])
        score.main()

    out_path = tmp_path / "data" / "scored" / "2026-W34.jsonl"
    lines = out_path.read_text().splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["section"] == "llm"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/test_score_main.py -v`
Expected: FAIL — `AttributeError: module 'score' has no attribute 'main'`

- [ ] **Step 3: Implement `main`**

Add to the top of `pipeline/score.py`: `import argparse`, `import sys`.

Append at the end of `pipeline/score.py`:

```python
def _load_source_tiers() -> dict[str, int]:
    import yaml

    with open("config/sources.yaml") as f:
        config = yaml.safe_load(f)
    tiers = {}
    for group in ("papers", "journals", "labs", "news", "security", "safety"):
        for source in config.get(group, []):
            tiers[source["id"]] = source["tier"]
    return tiers


def main() -> None:
    global SOURCE_TIERS
    import json
    import os

    parser = argparse.ArgumentParser()
    parser.add_argument("--week", required=True, help="ISO week, e.g. 2026-W34.")
    args = parser.parse_args()

    SOURCE_TIERS = _load_source_tiers()

    raw_items: list[RawItem] = []
    with open(f"data/raw/{args.week}.jsonl") as f:
        for line in f:
            raw_items.append(RawItem.model_validate_json(line))

    deduped = dedupe(raw_items)
    filtered = prefilter(deduped)
    scored = classify_and_score(filtered)
    ranked = rank(scored)

    os.makedirs("data/scored", exist_ok=True)
    with open(f"data/scored/{args.week}.jsonl", "w") as out:
        for item in ranked:
            out.write(item.model_dump_json() + "\n")

    print(f"week {args.week}: {len(raw_items)} raw -> {len(filtered)} prefiltered -> {len(ranked)} ranked")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python -m pytest tests/test_score_main.py -v`
Expected: PASS

- [ ] **Step 5: Run the full score test suite**

Run: `.venv/Scripts/python -m pytest tests/test_score_dedupe.py tests/test_score_prefilter.py tests/test_score_classify.py tests/test_score_rank.py tests/test_score_main.py -v`
Expected: all PASS

- [ ] **Step 6: Commit**

```bash
git add pipeline/score.py tests/test_score_main.py
git commit -m "feat: implement score.py main orchestration"
```

---

## Task 15: `pipeline/build.py` — `write_headline` and `build_issue`

**Files:**
- Modify: `pipeline/build.py`
- Test: `tests/test_build.py`

**Interfaces:**
- Consumes: `ScoredItem`, `Issue`, `Section` (`models.py`), `config/sources.yaml` section labels/blurbs, `week_bounds` (Task 2).
- Produces: `write_headline(items: list[ScoredItem]) -> str` and `build_issue(week: str, items: list[ScoredItem]) -> Issue`, both consumed by `main` (Task 16).

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_build.py
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_build.py -v`
Expected: FAIL — `NotImplementedError`

- [ ] **Step 3: Implement `write_headline` and `build_issue`**

Add `from anthropic import Anthropic` and `from datetime import datetime, timezone` to `pipeline/build.py`'s imports (alongside the existing `from models import Issue, ScoredItem`, extend to also import `Section`).

```python
_HEADLINE_PROMPT = """Write one sentence summarizing the most notable AI news \
this week for a practitioner digest. No hype, no "X: Y" colon-subtitle \
construction. If nothing stands out, say plainly that the week was quiet.

Top items this week, highest ranked first:
{items}
"""


def write_headline(items: list[ScoredItem]) -> str:
    """One LLM call over the top ~10 items. One sentence, no hype, no colon-
    then-subtitle construction. If nothing stands out, say the week was quiet.
    """
    top = sorted(items, key=lambda i: i.score, reverse=True)[:10]
    items_text = "\n".join(f"- [{i.section}] {i.title}: {i.why}" for i in top) or "(no items this week)"
    client = Anthropic()
    response = client.messages.create(
        model="claude-sonnet-5",
        max_tokens=256,
        messages=[{"role": "user", "content": _HEADLINE_PROMPT.format(items=items_text)}],
    )
    return "".join(block.text for block in response.content if block.type == "text").strip()


def _section_meta() -> dict[str, dict[str, str]]:
    import yaml

    with open("config/sources.yaml") as f:
        config = yaml.safe_load(f)
    return {s["id"]: {"label": s["label"], "blurb": s["blurb"]} for s in config["sections"]}


def build_issue(week: str, items: list[ScoredItem]) -> Issue:
    from collections import defaultdict

    from dates import week_bounds

    starts_on, ends_on = week_bounds(week)
    meta = _section_meta()

    by_section: dict[str, list[ScoredItem]] = defaultdict(list)
    for item in items:
        by_section[item.section].append(item)

    sections = [
        Section(
            id=section_id,
            label=meta[section_id]["label"],
            blurb=meta[section_id]["blurb"],
            items=sorted(section_items, key=lambda i: i.score, reverse=True),
        )
        for section_id, section_items in by_section.items()
        if section_items  # a section with 0 items renders as a quiet week, never padded
    ]
    # Stable order: whatever order sections.yaml declares them in.
    order = list(meta.keys())
    sections.sort(key=lambda s: order.index(s.id))

    return Issue(
        week=week,
        starts_on=starts_on,
        ends_on=ends_on,
        generated_at=datetime.now(timezone.utc),
        headline=write_headline(items),
        sections=sections,
        stats={"items_kept": len(items)},
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_build.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add pipeline/build.py tests/test_build.py
git commit -m "feat: implement build.write_headline and build.build_issue"
```

---

## Task 16: `pipeline/build.py` — `main` (atomic write, index/seen update)

**Files:**
- Modify: `pipeline/build.py` (add `main`)
- Test: `tests/test_build_main.py`

**Interfaces:**
- Consumes: `build_issue` (Task 15), `data/scored/<week>.jsonl`.
- Produces: `data/<week>.json` (atomic write), `data/index.json` (list of `{week, headline, generated_at}`, newest first), `data/seen.json` (accumulated `dedupe_key`s — needs `RawItem.dedupe_key`, so `build.py` re-derives it from each `ScoredItem`, which is a `RawItem` subclass).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_build_main.py
import json
from unittest.mock import patch

import build


def test_main_writes_issue_index_and_seen(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
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
    (tmp_path / "data" / "scored").mkdir(parents=True)
    (tmp_path / "data" / "scored" / "2026-W35.jsonl").write_text("")

    with patch("build.write_headline", return_value="Quiet week."):
        monkeypatch.setattr("sys.argv", ["build.py", "--week", "2026-W35"])
        build.main()

    assert not (tmp_path / "data" / ".2026-W35.json.tmp").exists()
    assert (tmp_path / "data" / "2026-W35.json").exists()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_build_main.py -v`
Expected: FAIL — `AttributeError: module 'build' has no attribute 'main'`

- [ ] **Step 3: Implement `main`**

Add `import argparse`, `import json`, `import os`, `import sys` to `pipeline/build.py`'s imports.

Append:

```python
def main() -> None:
    """Write atomically (tmp file + rename) so a crash never leaves the site
    reading a half-written issue.
    """
    from models import ScoredItem

    parser = argparse.ArgumentParser()
    parser.add_argument("--week", required=True, help="ISO week, e.g. 2026-W34.")
    args = parser.parse_args()

    items: list[ScoredItem] = []
    with open(f"data/scored/{args.week}.jsonl") as f:
        for line in f:
            if line.strip():
                items.append(ScoredItem.model_validate_json(line))

    issue = build_issue(args.week, items)

    tmp_path = f"data/.{args.week}.json.tmp"
    final_path = f"data/{args.week}.json"
    with open(tmp_path, "w") as f:
        f.write(issue.model_dump_json(indent=2))
    os.replace(tmp_path, final_path)

    index_path = "data/index.json"
    index = []
    if os.path.exists(index_path):
        with open(index_path) as f:
            index = json.load(f)
    index = [entry for entry in index if entry["week"] != args.week]
    index.insert(0, {"week": issue.week, "headline": issue.headline, "generated_at": issue.generated_at.isoformat()})
    index.sort(key=lambda e: e["week"], reverse=True)
    with open(index_path, "w") as f:
        json.dump(index, f, indent=2)

    seen_path = "data/seen.json"
    seen = set()
    if os.path.exists(seen_path):
        with open(seen_path) as f:
            seen = set(json.load(f))
    seen.update(item.dedupe_key for item in items)
    with open(seen_path, "w") as f:
        json.dump(sorted(seen), f, indent=2)

    print(f"built {final_path}: {len(items)} items across {len(issue.sections)} sections")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_build_main.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Run the full pipeline test suite**

Run: `.venv/Scripts/python -m pytest -v`
Expected: all PASS (every test file from Tasks 2–16)

- [ ] **Step 6: Commit**

```bash
git add pipeline/build.py tests/test_build_main.py
git commit -m "feat: implement build.py main with atomic write and index/seen tracking"
```

---

## Task 17: Sample issue data for site development

**Files:**
- Create: `data/2026-W34.json`
- Create: `data/index.json`
- Create: `data/seen.json`

**Interfaces:**
- Produces: one realistic `Issue` JSON matching `models.Issue`'s schema exactly, so Tasks 18–19 can build the Astro site against real-shaped data before the live pipeline has ever run (it can't — no `ANTHROPIC_API_KEY` is configured yet). This file is superseded the first time the real `weekly.yml` workflow runs; it is not deleted here.

- [ ] **Step 1: Generate the sample issue with a small script (not committed)**

Run this inline (do not save as a project file — it's a one-off generator):

```bash
.venv/Scripts/python - <<'PYEOF'
import json
import sys
sys.path.insert(0, "pipeline")
from datetime import datetime, timezone
from models import Issue, Section, ScoredItem

def item(section, title, why, score, url, mirrors=None, kind="paper"):
    return ScoredItem(
        source_id="sample", kind=kind, title=title, url=url,
        published_at="2026-08-19T00:00:00Z", section=section,
        score=score, why=why, mirrors=mirrors or [],
    )

sections = [
    Section(id="llm", label="LLM & reasoning", blurb="Models, training, benchmarks, agents", items=[
        item("llm", "Scaling laws for retrieval-augmented reasoning",
             "Retrieval quality now matters more than model size past 70B params.",
             0.91, "https://arxiv.org/abs/2508.01234",
             mirrors=["https://huggingface.co/papers/2508.01234"]),
        item("llm", "Anthropic ships constitutional classifiers v2",
             "Cuts jailbreak success rate by half with no latency cost.",
             0.84, "https://www.anthropic.com/news/constitutional-classifiers-v2", kind="release"),
    ]),
    Section(id="security", label="AI security", blurb="Supply chain, prompt injection, agent vulnerabilities", items=[
        item("security", "Poisoned MCP server found in three popular agent templates",
             "Exfiltrated API keys via a tool description; patched within 48 hours.",
             0.95, "https://www.wiz.io/blog/mcp-server-supply-chain", kind="advisory"),
    ]),
    Section(id="science", label="AI for science", blurb="Biology, materials, climate", items=[
        item("science", "Diffusion model proposes three stable new battery electrolytes",
             "All three synthesized and verified in the same paper — rare for generative chemistry.",
             0.78, "https://www.nature.com/articles/s41586-026-00042-x"),
    ]),
]

issue = Issue(
    week="2026-W34", starts_on="2026-08-17T00:00:00Z", ends_on="2026-08-24T00:00:00Z",
    generated_at=datetime.now(timezone.utc), headline="A supply-chain scare in MCP tooling overshadowed a quiet week for new model releases.",
    sections=sections, stats={"items_seen": 412, "items_kept": 4},
)

with open("data/2026-W34.json", "w") as f:
    f.write(issue.model_dump_json(indent=2))

with open("data/index.json", "w") as f:
    json.dump([{"week": "2026-W34", "headline": issue.headline, "generated_at": issue.generated_at.isoformat()}], f, indent=2)

with open("data/seen.json", "w") as f:
    json.dump([i.dedupe_key for s in sections for i in s.items], f, indent=2)

print("wrote sample data/2026-W34.json, data/index.json, data/seen.json")
PYEOF
```

- [ ] **Step 2: Verify the files exist and are valid JSON**

Run: `.venv/Scripts/python -c "import json; json.load(open('data/2026-W34.json')); json.load(open('data/index.json')); json.load(open('data/seen.json')); print('ok')"`
Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add data/2026-W34.json data/index.json data/seen.json
git commit -m "chore: add sample issue data for site development"
```

---

## Task 18: Astro site scaffold + design pass + responsive layout

**Files:**
- Create: `web/package.json`, `web/astro.config.mjs`, `web/tsconfig.json`
- Create: `web/src/layouts/Layout.astro`
- Create: `web/src/styles/global.css`
- Create: `web/src/lib/issues.ts`

**Interfaces:**
- Produces: `getAllIssues(): Issue[]` and `getIssue(week: string): Issue | undefined` in `web/src/lib/issues.ts`, reading `../../../data/*.json` via `import.meta.glob("../../../data/*.json", { eager: true })`. Both are consumed by every route in Task 19. `Layout.astro` provides the shared `<head>`, global CSS import, and page shell; every route wraps its content in it.

- [ ] **Step 1: Scaffold the Astro project**

```bash
cd /d/Projets/tentac/ai-weekly/web
npm create astro@latest . -- --template minimal --no-install --no-git --typescript strict --yes
npm install
```

- [ ] **Step 2: Design pass — record the palette and type choices as a comment block**

This project's subject is a technical, fast-moving digest (papers, security incidents, lab releases) — the design should read as a dense, well-organized signal feed, not a marketing page. Palette and type choices (write these into `global.css` in Step 4, don't skip them):

- Background `#0b1210` (near-black, slight green cast — nods to a terminal/monitoring aesthetic without going full hacker-green)
- Surface (cards) `#121b18`
- Text primary `#e8efe9`, text muted `#8fa89c`
- Accent `#5ee6b0` (signal green — used sparingly: section labels, the 🤖 AI-summary block border, link hover)
- Danger/security accent `#ff6b5e` (used only on the `security` section's items and CVE badges)
- Display face: `"Fraunces", Georgia, serif` (loaded from Google Fonts) for issue headlines and the AI-summary block — a serif with enough personality to feel edited, not templated
- Body face: `"Inter", -apple-system, sans-serif` for item titles, `why` lines, nav
- Signature element: each item card has a thin left border in its section's accent color (green by default, red for security) instead of a boxed card — makes a section scannable by color down the page, and is cheap to keep responsive

- [ ] **Step 3: Write `web/src/lib/issues.ts`**

```typescript
export interface ScoredItemData {
  source_id: string;
  kind: string;
  title: string;
  url: string;
  published_at: string;
  summary: string;
  authors: string[];
  meta: Record<string, unknown>;
  section: string;
  score: number;
  why: string;
  mirrors: string[];
}

export interface SectionData {
  id: string;
  label: string;
  blurb: string;
  items: ScoredItemData[];
}

export interface IssueData {
  week: string;
  starts_on: string;
  ends_on: string;
  generated_at: string;
  headline: string;
  sections: SectionData[];
  stats: Record<string, unknown>;
}

const modules = import.meta.glob<{ default: IssueData }>("../../../data/*.json", { eager: true });

function isIssueFile(path: string): boolean {
  // data/index.json and data/seen.json are not issues.
  return /\/data\/\d{4}-W\d{2}\.json$/.test(path);
}

export function getAllIssues(): IssueData[] {
  return Object.entries(modules)
    .filter(([path]) => isIssueFile(path))
    .map(([, mod]) => mod.default)
    .sort((a, b) => (a.week < b.week ? 1 : -1));
}

export function getIssue(week: string): IssueData | undefined {
  return getAllIssues().find((issue) => issue.week === week);
}
```

- [ ] **Step 4: Write `web/src/styles/global.css`**

```css
@import url("https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,400;9..144,600&family=Inter:wght@400;500;600&display=swap");

:root {
  --bg: #0b1210;
  --surface: #121b18;
  --text: #e8efe9;
  --text-muted: #8fa89c;
  --accent: #5ee6b0;
  --danger: #ff6b5e;
  --font-display: "Fraunces", Georgia, serif;
  --font-body: "Inter", -apple-system, BlinkMacSystemFont, sans-serif;
}

* { box-sizing: border-box; }

body {
  margin: 0;
  background: var(--bg);
  color: var(--text);
  font-family: var(--font-body);
  line-height: 1.5;
}

a { color: var(--accent); }
a:hover { text-decoration: underline; }

:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 2px;
}

.container {
  max-width: 44rem;
  margin: 0 auto;
  padding: 1.5rem 1rem 4rem;
}

@media (min-width: 640px) {
  .container { padding: 2.5rem 1.5rem 5rem; }
}

.ai-summary {
  font-family: var(--font-display);
  font-size: 1.15rem;
  border-left: 3px solid var(--accent);
  background: var(--surface);
  padding: 1rem 1.25rem;
  border-radius: 0 6px 6px 0;
  margin: 1.5rem 0 2rem;
}

.ai-summary .robot { margin-right: 0.4em; }

.section-block { margin-bottom: 2.5rem; }

.section-block h2 {
  font-family: var(--font-display);
  font-size: 1.4rem;
  margin-bottom: 0.25rem;
}

.section-block .blurb {
  color: var(--text-muted);
  font-size: 0.9rem;
  margin-top: 0;
}

.item-card {
  border-left: 3px solid var(--accent);
  padding: 0.6rem 0 0.6rem 1rem;
  margin-bottom: 1rem;
}

.item-card.security { border-left-color: var(--danger); }

.item-card .why {
  font-size: 1.05rem;
  font-weight: 500;
  margin: 0 0 0.25rem;
}

.item-card .title-link {
  color: var(--text-muted);
  font-size: 0.9rem;
  text-decoration: none;
}

.item-card .title-link:hover { color: var(--accent); }

.item-card .mirrors {
  font-size: 0.8rem;
  color: var(--text-muted);
  margin-top: 0.25rem;
}

.item-card .mirrors a { margin-right: 0.75rem; }

@media (prefers-reduced-motion: reduce) {
  * { transition: none !important; animation: none !important; }
}
```

- [ ] **Step 5: Write `web/src/layouts/Layout.astro`**

```astro
---
import "../styles/global.css";

interface Props {
  title: string;
}
const { title } = Astro.props;
---
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>{title}</title>
  </head>
  <body>
    <div class="container">
      <slot />
    </div>
  </body>
</html>
```

- [ ] **Step 6: Verify the dev server starts**

```bash
cd /d/Projets/tentac/ai-weekly/web
npm run dev -- --port 4321 &
sleep 3
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:4321/
kill %1
```

Expected: `200` (route `/` doesn't exist yet — Astro's minimal template default page still responds at this point; a 404 is also acceptable here since Task 19 adds the real route next. A connection failure is not.)

- [ ] **Step 7: Commit**

```bash
git add web/package.json web/package-lock.json web/astro.config.mjs web/tsconfig.json web/src
git commit -m "feat: scaffold Astro site with design pass and shared layout"
```

---

## Task 19: Astro routes — `/`, `/w/[week]`, `/archive`, `/rss.xml`

**Files:**
- Create: `web/src/components/ItemCard.astro`
- Create: `web/src/components/SectionBlock.astro`
- Create: `web/src/pages/index.astro`
- Create: `web/src/pages/w/[week].astro`
- Create: `web/src/pages/archive.astro`
- Create: `web/src/pages/rss.xml.js`

**Interfaces:**
- Consumes: `getAllIssues`, `getIssue`, `IssueData`, `SectionData`, `ScoredItemData` (Task 18), `Layout.astro` (Task 18).

- [ ] **Step 1: Write `web/src/components/ItemCard.astro`**

```astro
---
import type { ScoredItemData } from "../lib/issues";

interface Props {
  item: ScoredItemData;
  sectionId: string;
}
const { item, sectionId } = Astro.props;
---
<div class:list={["item-card", { security: sectionId === "security" }]}>
  <p class="why">{item.why}</p>
  <a class="title-link" href={item.url} target="_blank" rel="noopener">{item.title} &rarr;</a>
  {item.mirrors.length > 0 && (
    <p class="mirrors">
      also:
      {item.mirrors.map((mirrorUrl, i) => (
        <a href={mirrorUrl} target="_blank" rel="noopener">source {i + 2}</a>
      ))}
    </p>
  )}
</div>
```

- [ ] **Step 2: Write `web/src/components/SectionBlock.astro`**

```astro
---
import type { SectionData } from "../lib/issues";
import ItemCard from "./ItemCard.astro";

interface Props {
  section: SectionData;
}
const { section } = Astro.props;
---
<section class="section-block">
  <h2>{section.label}</h2>
  <p class="blurb">{section.blurb}</p>
  {section.items.map((item) => <ItemCard item={item} sectionId={section.id} />)}
</section>
```

- [ ] **Step 3: Write `web/src/pages/index.astro`**

```astro
---
import Layout from "../layouts/Layout.astro";
import SectionBlock from "../components/SectionBlock.astro";
import { getAllIssues } from "../lib/issues";

const issues = getAllIssues();
const latest = issues[0];
---
<Layout title={latest ? `ai-weekly — ${latest.week}` : "ai-weekly"}>
  {latest ? (
    <>
      <h1>ai-weekly</h1>
      <p class="ai-summary"><span class="robot">🤖</span>{latest.headline}</p>
      {latest.sections.map((section) => <SectionBlock section={section} />)}
      <p><a href="/archive">See every past issue &rarr;</a></p>
    </>
  ) : (
    <p>No issue published yet.</p>
  )}
</Layout>
```

- [ ] **Step 4: Write `web/src/pages/w/[week].astro`**

```astro
---
import Layout from "../../layouts/Layout.astro";
import SectionBlock from "../../components/SectionBlock.astro";
import { getAllIssues, getIssue } from "../../lib/issues";

export function getStaticPaths() {
  return getAllIssues().map((issue) => ({ params: { week: issue.week } }));
}

const { week } = Astro.params;
const issue = getIssue(week!);
if (!issue) throw new Error(`no issue for week ${week}`);
---
<Layout title={`ai-weekly — ${issue.week}`}>
  <h1>ai-weekly — {issue.week}</h1>
  <p class="ai-summary"><span class="robot">🤖</span>{issue.headline}</p>
  {issue.sections.map((section) => <SectionBlock section={section} />)}
  <p><a href="/archive">See every past issue &rarr;</a></p>
</Layout>
```

- [ ] **Step 5: Write `web/src/pages/archive.astro`**

```astro
---
import Layout from "../layouts/Layout.astro";
import { getAllIssues } from "../lib/issues";

const issues = getAllIssues();
---
<Layout title="ai-weekly — archive">
  <h1>Archive</h1>
  <ul>
    {issues.map((issue) => (
      <li>
        <a href={`/w/${issue.week}`}>{issue.week}</a> — {issue.headline}
      </li>
    ))}
  </ul>
  <p><a href="/rss.xml">RSS feed &rarr;</a></p>
</Layout>
```

- [ ] **Step 6: Write `web/src/pages/rss.xml.js`**

```javascript
import { getAllIssues } from "../lib/issues.ts";

export async function GET(context) {
  const issues = getAllIssues();
  const siteUrl = context.site?.toString().replace(/\/$/, "") ?? "";
  const items = issues
    .map(
      (issue) => `
    <item>
      <title>ai-weekly — ${issue.week}</title>
      <link>${siteUrl}/w/${issue.week}</link>
      <guid>${siteUrl}/w/${issue.week}</guid>
      <pubDate>${new Date(issue.generated_at).toUTCString()}</pubDate>
      <description><![CDATA[${issue.headline}]]></description>
    </item>`
    )
    .join("");

  const body = `<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel>
  <title>ai-weekly</title>
  <link>${siteUrl}</link>
  <description>A weekly digest of what happened in AI.</description>
  ${items}
</channel></rss>`;

  return new Response(body, { headers: { "Content-Type": "application/xml" } });
}
```

- [ ] **Step 7: Set `site` in `astro.config.mjs` for RSS absolute URLs**

Edit `web/astro.config.mjs` to add the Pages URL:

```javascript
import { defineConfig } from "astro/config";

export default defineConfig({
  site: "https://baiddd.github.io/tentac",
});
```

- [ ] **Step 8: Build and verify all four routes render**

```bash
cd /d/Projets/tentac/ai-weekly/web
npm run build
ls dist/index.html dist/archive/index.html dist/w/2026-W34/index.html dist/rss.xml
```

Expected: all four paths exist. Then spot-check content:

```bash
grep -q "🤖" dist/index.html && echo "AI summary block present"
grep -q "arxiv.org/abs/2508.01234" dist/index.html && echo "clickable source present"
```

Expected: both echo lines print.

- [ ] **Step 9: Responsive + accessibility spot-check**

```bash
npm run preview -- --port 4321 &
sleep 3
curl -s http://localhost:4321/ | grep -q 'name="viewport"' && echo "viewport meta present"
kill %1
```

Manually confirm in a browser at a 360px-wide viewport once deployed (Task 20) that item cards don't overflow horizontally and the AI-summary block wraps correctly — the CSS above uses a fluid `.container` with no fixed-width children, so no horizontal scroll is expected, but verify after deploy since this is the first real render.

- [ ] **Step 10: Commit**

```bash
git add web/src/components web/src/pages web/astro.config.mjs
git commit -m "feat: add site routes (/, /w/[week], /archive, /rss.xml)"
```

---

## Task 20: Push, verify Pages deploy, hand off pipeline secrets to the user

**Files:** none (verification + handoff task)

**Interfaces:** none — this task closes the loop between the repo (Task 1) and the live site (Task 19).

- [ ] **Step 1: Push everything**

```bash
cd /d/Projets/tentac/ai-weekly
git push
```

- [ ] **Step 2: Trigger the deploy workflow and watch it**

```bash
gh workflow run deploy.yml
gh run watch --exit-status
```

Expected: the run succeeds. If it fails on `npm ci` because `web/package-lock.json` is missing or out of date, run `npm install` in `web/` locally, commit the resulting `package-lock.json`, push, and re-run.

- [ ] **Step 3: Confirm the live URL serves the site**

```bash
curl -s -o /dev/null -w "%{http_code}\n" https://baiddd.github.io/tentac/
```

Expected: `200`. (Pages can take a minute after the first successful deploy to become reachable — retry once after 60s if it 404s immediately.)

- [ ] **Step 4: Hand off the two manual steps only the user can do**

Report to the user (do not attempt these yourself — they require the user's own Anthropic account):

1. Add the `ANTHROPIC_API_KEY` repo secret: `gh secret set ANTHROPIC_API_KEY` (prompts for the value on stdin), or via the GitHub UI at Settings → Secrets and variables → Actions.
2. Once the secret is set, trigger the real pipeline once manually before trusting the Monday cron: `gh workflow run weekly.yml -f week=2026-W34`, then `gh run watch --exit-status`. Confirm `data/2026-W34.json` gets overwritten with real (not sample) content and committed by the `ai-weekly-bot` user, and that `deploy.yml` fires automatically off that commit.

- [ ] **Step 5: No commit — this task only verifies and reports.**

---

## Self-Review Notes (already applied above)

- **Spec coverage:** Phase 0 → Tasks 2–3. Phase 1 → Tasks 4–9. Phase 2 → Tasks 10–14. Phase 3 → Tasks 17–19 (routes, design pass, responsive/focus/reduced-motion floor, clickable sources+mirrors, 🤖 AI-summary block). Phase 4 → Task 20 (workflows were already scaffolded; this task is the "verify in this order" checklist from PLAN.md). Phase 5 is out of scope per the Goal section.
- **Type consistency checked:** `ScoredItem.mirrors` (Task 12) is populated from `RawItem.meta["mirror_urls"]`, which `dedupe` (Task 10) is the sole writer of — confirmed the key name matches across both tasks. `SOURCE_TIERS` / `_tier()` (Task 10) is reused unchanged by `prefilter` (Task 11) and `rank` (Task 13). `week_bounds` / `current_week` (Task 2) signatures match every caller in Tasks 9 and 15.
- **No placeholders:** every step above contains runnable code; the one deliberately deferred item (tenacity retry wrapping in Task 9) is called out explicitly as an optional follow-up, not left as a silent gap in a task's "done" criteria.
