"""Stage 3 — assemble the issue and write the artifact the site reads.

Output:
  data/<week>.json        the issue
  data/index.json         list of all weeks, newest first
  data/seen.json          dedupe_keys already published, so items don't repeat
"""

from __future__ import annotations

from models import Issue, ScoredItem


def write_headline(items: list[ScoredItem]) -> str:
    """One LLM call over the top ~10 items. One sentence, no hype, no colon-
    then-subtitle construction. If nothing stands out, say the week was quiet.
    """
    raise NotImplementedError


def build_issue(week: str, items: list[ScoredItem]) -> Issue:
    raise NotImplementedError


def main() -> None:
    """Write atomically (tmp file + rename) so a crash never leaves the site
    reading a half-written issue.
    """
    raise NotImplementedError


if __name__ == "__main__":
    main()
