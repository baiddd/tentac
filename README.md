# tentac

**Live site: https://baiddd.github.io/tentac/**

A weekly digest of what happened in AI — papers, journals, lab blogs, and
security research, picked and summarized by Claude. No `ANTHROPIC_API_KEY`
anywhere: fetching is automated, the AI classification step is done
locally via Claude Code, and the result is reviewed as a normal pull
request before it goes live.

(The codebase and Python package are still internally named `ai-weekly` —
that's the pipeline's name, not the site's brand. Only user-facing text
— page titles, headings, the RSS feed — says "tentac".)

- `config/sources.yaml` — every source, grouped by section, with a tier
- `pipeline/` — fetch → score → build
- `data/` — one committed JSON file per week; the archive is the git history
- `web/` — Astro site published to GitHub Pages
- `.claude/skills/weekly-analysis/` — the local, no-API-key classification step

## How a weekly issue happens

1. **Automatic (GitHub Actions, every Monday 06:00 UTC, no secrets needed):**
   `fetch.yml` runs `pipeline/fetch.py` then `pipeline/score.py --stage
   prefilter` (dedupe + prefilter — pure code, no LLM), and opens a PR on a
   branch named `issue/<week>` with `data/raw/<week>.jsonl` and
   `data/prefiltered/<week>.jsonl`.
2. **Local, via Claude Code (no API key — uses your own Claude Code
   session):**
   ```bash
   git fetch && git checkout issue/2026-W34
   ```
   Open Claude Code in the repo and run `/weekly-analysis`. It classifies
   and scores every item, checks that each source link actually resolves
   (drops dead links), ranks them, writes the headline, and assembles
   `data/2026-W34.json`. Review the diff, commit, and push to the same
   branch.
3. **Merge the PR.** Merging to `main` triggers `deploy.yml` (GitHub
   Actions), which builds the Astro site and publishes it to GitHub
   Pages automatically — no manual deploy step.

## Local run (manual, for testing a single stage)

```bash
python -m venv .venv && .venv/Scripts/pip install -r requirements-dev.txt   # or .venv/bin/pip on macOS/Linux
.venv/Scripts/python pipeline/fetch.py --week 2026-W34        # or --date 2026-08-24
.venv/Scripts/python pipeline/score.py --week 2026-W34 --stage prefilter
# then run the /weekly-analysis Claude Code skill, or manually:
.venv/Scripts/python pipeline/score.py --week 2026-W34 --stage rank
.venv/Scripts/python pipeline/build.py --week 2026-W34 --headline "..."
```

`classify_and_score()` (in `pipeline/score.py`) and `write_headline()` (in
`pipeline/build.py`) still exist and are fully unit-tested — they call the
`anthropic` SDK directly and need a real `ANTHROPIC_API_KEY`. Nothing in
this repo's default workflow calls them; they're there for anyone who
later wants to fully automate the classification step in CI instead of
doing it locally via Claude Code.

## Setup (one-time)

1. Enable Pages: Settings → Pages → source **GitHub Actions**.
2. Trigger `Fetch weekly issue` manually once
   (`gh workflow run fetch.yml`) to confirm the PR-opening flow works,
   before relying on the Monday cron.
