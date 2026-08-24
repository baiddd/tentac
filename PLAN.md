# ai-weekly — implementation plan

A weekly digest of what happened in AI, built from papers, journals, lab blogs,
and security research. Static site, no backend, deployed from the repo.

**How to use this file:** paste it into Claude Code as the working spec, then
work phase by phase. Every stub in `pipeline/` raises `NotImplementedError` and
carries a docstring describing exactly what it should do. Fill them in order.
Do not skip Phase 0.

---

## Architecture

```
GitHub Actions (cron, Mondays 06:00 UTC)
    │
    ├─ fetch.py    sources.yaml ──► data/raw/<week>.jsonl
    ├─ score.py    dedupe, classify, rank ──► data/scored/<week>.jsonl
    └─ build.py    assemble ──► data/<week>.json  (committed to the repo)
                                      │
                                      ▼
                        Astro static build ──► GitHub Pages
```

No database, no server, no hosting cost. The issue history is the git history.

## Repo layout

```
ai-weekly/
├── PLAN.md                      this file
├── requirements.txt
├── config/sources.yaml          source registry — sections, feeds, tiers
├── pipeline/
│   ├── models.py                pydantic schema shared by all stages
│   ├── fetch.py                 stage 1 — collect
│   ├── score.py                 stage 2 — dedupe, classify, rank
│   └── build.py                 stage 3 — assemble the issue
├── data/                        committed issues + index.json + seen.json
├── web/                         Astro site (to scaffold in Phase 3)
└── .github/workflows/
    ├── weekly.yml               build + commit the issue
    └── deploy.yml               build + publish the site
```

## Sections

Eight, defined in `config/sources.yaml`. Two notes on the split:

- **Security** and **Safety** are separate. Security is supply-chain attacks,
  prompt injection, agent vulnerabilities — daily cadence, vendor research
  blogs break it first. Safety is evals, interpretability, governance — weekly
  to monthly, closer to papers. Merging them buries one under the other.
- A section with no items renders as a quiet week. Never pad a section to fill
  it; padding is how a digest loses trust.

---

## Phase 0 — foundations

1. `git init`, push to GitHub, enable Pages (Settings → Pages → source: GitHub Actions).
2. Add repo secret `ANTHROPIC_API_KEY`. `GITHUB_TOKEN` is provided automatically.
3. Implement `RawItem.dedupe_key` in `models.py` — everything downstream depends
   on it. Preference order: DOI > arXiv ID > CVE ID > normalized URL (strip
   `utm_*`, trailing slash, `www.`, and arXiv version suffix `v2`).
4. Write `week_bounds(week: str) -> tuple[datetime, datetime]`. ISO weeks, UTC,
   half-open interval `[monday, next monday)`. Put it in a `pipeline/dates.py`.
   Get this right once; every stage uses it.

**Done when:** `pytest` passes on dedupe_key and week_bounds, including the
year-boundary case (2026-W01 starts 2025-12-29).

## Phase 1 — fetch

Implement `fetch_rss` and `fetch_arxiv` first and nothing else. Run against a
real week. Look at the output by hand before writing another fetcher.

- Per-source try/except. One dead feed must never fail the run — log the source
  id and the exception, keep going, and record failures in the run stats.
- `tenacity` retry on network errors, 3 attempts, exponential backoff.
- arXiv rate limit: 3 seconds between calls, non-negotiable, they will block you.
- Cache ETag / Last-Modified under `.cache/` keyed by source id.
- Scrapers last. Keep every CSS selector in one `SELECTORS` dict in `fetch.py`
  so breakage is visible and repairable in one place.

**Done when:** one week of `cs.CL` + Nature + HF Daily lands in
`data/raw/<week>.jsonl` with correct timestamps and no duplicate URLs.

## Phase 2 — score (the part that decides if this is any good)

`cs.CL` alone produces roughly 400 papers a week. Everything here is about
getting to ~40 items worth reading.

1. **Dedupe.** Exact on `dedupe_key`, then near-dupe titles via
   `rapidfuzz.token_set_ratio >= 92`. The same paper arrives from arXiv, HF
   Daily Papers, and a lab blog — collapse into one item, keep the highest-tier
   source as canonical, push the rest into `mirrors`.
2. **Prefilter, before spending any tokens.** Target 400+ → ~120. Drop items
   with no abstract and arXiv revisions already published in a past issue
   (`data/seen.json`). Auto-keep tier-1 sources, anything carrying a CVE, and
   HF upvotes ≥ 30.
3. **Classify + score.** One batched Claude call per ~20 items, strict JSON out:
   `{"url", "section", "score" (0..1), "why" (≤20 words)}`. Validate `section`
   against the `SectionId` literal and drop malformed rows rather than trusting
   the response shape. The scoring question is "would a working practitioner
   regret missing this", not "is this well written".
4. **Rank.** `0.55 * model_score + 0.25 * social + 0.20 * source_tier`, where
   social is log-normalized HF upvotes / GitHub stars. Cap 6 items per section,
   8 for security during an active incident.

**Calibration step, do not skip:** run Phase 2 over three past weeks and read
the top 10 of each yourself. If you disagree with more than two placements, the
prompt is wrong, not the ranking formula. Fix the prompt first.

## Phase 3 — the site

Astro with zero client JS by default. Read `data/*.json` at build time via
`import.meta.glob` — no fetch at runtime, no loading states.

Routes:
- `/` — latest issue
- `/w/[week]` — a past issue
- `/archive` — every issue, newest first
- `/rss.xml` — your own feed, so the digest is itself subscribable

Before writing any CSS, do a design pass: pick a palette of 4–6 named hex
values, a display face and a body face chosen for this subject specifically,
and one signature element the page is remembered by. Avoid the current
AI-default looks — cream background with a warm-clay accent, near-black with
one acid accent, or a broadsheet grid of hairline rules. Each item shows its
`why` line as the primary text; the title is secondary. The reader should be
able to scan a section in ten seconds and know whether to open anything.

Quality floor, unannounced: responsive to mobile, visible keyboard focus,
`prefers-reduced-motion` respected.

## Phase 4 — automation

Both workflows are already written. Verify in this order:

1. `workflow_dispatch` on `weekly.yml` with an explicit `--week`, confirm the
   issue JSON is committed.
2. Confirm `deploy.yml` fires on that commit and the site updates.
3. Only then trust the cron.

Write the issue atomically — temp file plus rename — so a crash never leaves
the site reading half a file.

## Phase 5 — worth having, once it runs

- Email digest via Buttondown API, driven from the same issue JSON.
- Per-section RSS, so a reader can take security only.
- A `notable` flag that pins a major incident to the top of the issue.

---

## Things that will bite you

- **OpenReview is bursty, not weekly.** NeurIPS/ICLR/ICML decisions land in
  annual waves. An empty result is the normal case; treat a wave as a special
  edition rather than expecting steady volume.
- **Nature's RSS is the whole journal.** Most items are not AI. Filter hard or
  the science section fills with unrelated papers.
- **The LLM will invent section names.** Validate against the literal every time.
- **Scrapers break silently.** A source returning zero items for two consecutive
  weeks should surface as a warning in the run stats, not pass quietly.
- **If the app calls several model providers, you will reach for LiteLLM.** Pin
  a version published after March 2026, verify the hash, and use a lockfile
  with hashes — that incident is literally what your security section covers.
