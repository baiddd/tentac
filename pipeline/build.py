"""Stage 3 — assemble the issue and write the artifact the site reads.

Output:
  data/<week>.json        the issue
  data/index.json         list of all weeks, newest first
  data/seen.json          dedupe_keys already published, so items don't repeat
"""

from __future__ import annotations

from datetime import datetime, timezone

from anthropic import Anthropic

from models import Issue, ScoredItem, Section


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


def build_issue(
    week: str,
    items: list[ScoredItem],
    headline: str | None = None,
    analyzed_by: str | None = None,
    section_summaries: dict[str, str] | None = None,
) -> Issue:
    """Assemble the issue. `headline`, if given, is used as-is (no LLM call) —
    this is how the no-API-key workflow supplies a headline written locally
    by Claude Code. Omit it to fall back to `write_headline` (an LLM call),
    for a fully-automated path with a real ANTHROPIC_API_KEY. `analyzed_by`,
    if given, is recorded in `stats["analyzed_by"]` — the site shows it as a
    small credit line under the AI-summary block (e.g. "claude-sonnet-5").
    `section_summaries`, if given, maps a `SectionId` to a one-sentence
    recap shown under that section's heading on the site (`Section.summary`)
    — missing keys just leave that section's summary empty, never an error.
    """
    from collections import defaultdict

    from dates import week_bounds

    starts_on, ends_on = week_bounds(week)
    meta = _section_meta()
    section_summaries = section_summaries or {}

    by_section: dict[str, list[ScoredItem]] = defaultdict(list)
    for item in items:
        by_section[item.section].append(item)

    sections = [
        Section(
            id=section_id,
            label=meta[section_id]["label"],
            blurb=meta[section_id]["blurb"],
            items=sorted(section_items, key=lambda i: i.score, reverse=True),
            summary=section_summaries.get(section_id, ""),
        )
        for section_id, section_items in by_section.items()
        if section_items  # a section with 0 items renders as a quiet week, never padded
    ]
    # Stable order: whatever order sections.yaml declares them in.
    order = list(meta.keys())
    sections.sort(key=lambda s: order.index(s.id))

    stats = {"items_kept": len(items)}
    if analyzed_by:
        stats["analyzed_by"] = analyzed_by

    return Issue(
        week=week,
        starts_on=starts_on,
        ends_on=ends_on,
        generated_at=datetime.now(timezone.utc),
        headline=headline if headline is not None else write_headline(items),
        sections=sections,
        stats=stats,
    )


def main() -> None:
    """Write atomically (tmp file + rename) so a crash never leaves the site
    reading a half-written issue.
    """
    raise NotImplementedError


if __name__ == "__main__":
    main()
