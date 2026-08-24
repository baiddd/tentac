# ai-weekly

A weekly digest of what happened in AI — papers, journals, lab blogs, and
security research — assembled by a cron job and served as a static site.

- `config/sources.yaml` — every source, grouped by section, with a tier
- `pipeline/` — fetch → score → build
- `data/` — one committed JSON file per week; the archive is the git history
- `web/` — Astro site published to GitHub Pages

See `PLAN.md` for the implementation plan.

## Local run

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=...
python pipeline/fetch.py --week 2026-W34
python pipeline/score.py --week 2026-W34
python pipeline/build.py --week 2026-W34
```

## Setup

1. Enable Pages: Settings → Pages → source **GitHub Actions**
2. Add the repo secret `ANTHROPIC_API_KEY`
3. Trigger `Build weekly issue` manually once before relying on the cron
