---
name: weekly-analysis
description: Classify, score, rank, and write the headline for a prefiltered weekly ai-weekly issue — the local, no-API-key step in the fetch → PR → local analysis → merge → deploy workflow. Use when checked out on an `issue/<week>` branch (opened automatically by the fetch.yml GitHub Action) with a `data/prefiltered/<week>.jsonl` file present and no matching `data/<week>.json` yet.
---

# Weekly Analysis

This skill does the one step in the ai-weekly pipeline that needs a model:
classifying, scoring, and ranking each prefiltered item, and writing the
issue's one-sentence headline. It does this **directly, as you (Claude)
reasoning over the items** — it does not call the Anthropic API via the
`anthropic` Python SDK, and no `ANTHROPIC_API_KEY` is needed anywhere in
this workflow. `pipeline/score.py`'s `classify_and_score()` and
`pipeline/build.py`'s `write_headline()` functions still exist in the repo
(fully unit-tested) for anyone who later wants full CI automation with a
real API key, but this skill does the same job without one.

## When this runs

`fetch.yml` (GitHub Actions, cron every Monday) already ran `fetch.py` and
`score.py --stage prefilter`, and opened a PR on a branch named
`issue/<week>` containing `data/raw/<week>.jsonl` and
`data/prefiltered/<week>.jsonl`. You checked that branch out locally
(`git fetch && git checkout issue/<week>`) and are now running this skill
to finish the issue before merging the PR.

## Steps

1. **Find the week.** Read the current branch name (`git branch
   --show-current`) — it's `issue/<week>`. Confirm
   `data/prefiltered/<week>.jsonl` exists. If you can't determine the week
   this way, ask the user.

2. **Read the prefiltered items.** Load every line of
   `data/prefiltered/<week>.jsonl` — each line is a `RawItem` (see
   `pipeline/models.py` for the exact schema: `source_id`, `kind`, `title`,
   `url`, `published_at`, `summary`, `authors`, `meta`).

3. **Check each URL actually resolves before spending any judgment on it.**
   For every item, run a fast existence check — `curl -s -o /dev/null -w
   "%{http_code}" --max-time 10 -L "<url>"` (the `-L` follows redirects,
   which is normal and fine). Treat `200`–`399` as alive. Treat `404`,
   other `4xx`/`5xx`, a timeout, or a connection failure as dead — **drop
   that item entirely** (don't classify/score/rank a link nobody can open).
   Batch these checks (a handful of parallel `curl` calls, or one per
   Bash call in quick succession) rather than one at a time serially if
   there are many items. Keep a count of how many items you dropped this
   way and why — you'll report it at the end.

4. **Classify, score, and write the editorial line for every surviving
   item.** For each item, decide:
   - `section`: exactly one of `llm`, `vision`, `multimodal`, `systems`,
     `science`, `security`, `safety`, `industry` (the `SectionId` literal
     in `pipeline/models.py`). The item's `meta`/source in
     `config/sources.yaml` gives a prior — use it, but pick whichever
     section actually fits the content. Security vs safety: an exploited
     vulnerability or a live incident is `security`; an eval, a policy, or
     interpretability work is `safety`.
   - `score`: 0.0–1.0. The question is "would a working practitioner
     regret missing this" — not "is this well written."
   - `why`: ≤20 words, the line the reader actually sees. State what
     changed. No hedging, no "this paper proposes..." framing.
   - Carry over `meta.mirror_urls` (if present, set by `score.dedupe`)
     into a `mirrors` list of URLs.
   Write the result as one `ScoredItem` JSON object per line (same fields
   as `RawItem`, plus `section`, `score`, `why`, `mirrors`) to
   `data/scored/<week>.jsonl`, overwriting any existing content.

5. **Rank.** Run `python pipeline/score.py --week <week> --stage rank`
   (from the repo root, using the project's `.venv`:
   `.venv/Scripts/python pipeline/score.py --week <week> --stage rank` on
   Windows, `.venv/bin/python ...` on macOS/Linux). This applies the
   deterministic `0.55*score + 0.25*social + 0.20*source_tier` formula and
   caps items per section — pure code, no LLM, don't try to do this step
   yourself.

6. **Write the headline and a per-section summary.** Read the ranked
   `data/scored/<week>.jsonl`, group by `section`. Write:
   - One overall headline sentence (top ~10 items across all sections): no
     hype, no "X: Y" colon-subtitle construction. If nothing stands out,
     say plainly that the week was quiet.
   - One short sentence per section that ended up with items, recapping
     what that section's items add up to this week (not just restating
     one item's `why` — synthesize across the section). Skip sections
     with zero items entirely; don't write a summary for an empty
     section.

7. **Build the issue.** Run (escaping quotes for your shell as needed):
   ```
   .venv/Scripts/python pipeline/build.py --week <week> --headline "<your headline>" --analyzed-by "<your model name, e.g. claude-sonnet-5>" --section-summaries '{"llm": "<...>", "security": "<...>"}'
   ```
   This assembles `data/<week>.json` atomically and updates
   `data/index.json` / `data/seen.json` — no LLM call, `--headline` skips
   `write_headline()` entirely. `--analyzed-by` is shown on the site as a
   small credit line under the AI-summary block — pass your own model
   name if you know it (check your system prompt/context for it), or omit
   the flag if you're unsure. `--section-summaries` takes a JSON object
   keyed by section id (only include keys for sections that actually have
   items this week); each value renders under that section's heading on
   the site. Omit the flag entirely if you'd rather skip per-section
   summaries for this run — sections just render without one.

8. **Report to the user.** Summarize: how many items came in prefiltered,
   how many were dropped for dead links (and which ones, briefly), how many
   made the final ranked issue, the headline you wrote, and remind them to:
   - review the diff (`git diff`, or open `data/<week>.json`),
   - `git add data/scored data/<week>.json data/index.json data/seen.json`
     and commit,
   - `git push`,
   - review and merge the PR on GitHub (`gh pr merge` or the web UI) —
     merging triggers `deploy.yml` automatically, no further action needed.

## Things to get right

- Never invent an item that wasn't in `data/prefiltered/<week>.jsonl`.
- Never pad a section to fill it — a section with zero surviving items is
  a quiet week and should simply not appear (Task 15's `build_issue`
  already handles this; just don't force items into a section that
  doesn't fit).
- The dead-link check (step 3) is a judgment call on live network state at
  the moment you run it, not on the content — don't second-guess an item
  because you don't personally recognize the source, only because its URL
  didn't resolve.
