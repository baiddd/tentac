from datetime import datetime, timezone

import respx
import httpx

from fetch import fetch_github_advisories

GRAPHQL_RESPONSE = {
    "data": {
        "securityVulnerabilities": {
            "pageInfo": {"hasNextPage": False, "endCursor": None},
            "nodes": [
                {
                    "updatedAt": "2026-08-18T00:00:00Z",
                    "advisory": {
                        "ghsaId": "GHSA-xxxx-yyyy-zzzz",
                        "summary": "Malicious package",
                        "publishedAt": "2026-08-18T00:00:00Z",
                        "permalink": "https://github.com/advisories/GHSA-xxxx-yyyy-zzzz",
                        "identifiers": [{"type": "CVE", "value": "CVE-2026-99999"}],
                    },
                }
            ],
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
    # Same advisory is returned for both PIP and NPM queries; dedupe on
    # ghsaId collapses it to a single item.
    assert len(items) == 1
    assert items[0].kind == "advisory"
    assert items[0].meta["cve_ids"] == ["CVE-2026-99999"]


@respx.mock
def test_fetch_github_advisories_excludes_old_advisory_updated_this_week(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "test-token")
    old_advisory_updated_recently = {
        "data": {
            "securityVulnerabilities": {
                "pageInfo": {"hasNextPage": False, "endCursor": None},
                "nodes": [
                    {
                        "updatedAt": "2026-08-18T00:00:00Z",
                        "advisory": {
                            "ghsaId": "GHSA-old-old-old",
                            "summary": "Old advisory, just edited",
                            "publishedAt": "2020-01-01T00:00:00Z",
                            "permalink": "https://github.com/advisories/GHSA-old-old-old",
                            "identifiers": [],
                        },
                    }
                ],
            }
        }
    }
    respx.post("https://api.github.com/graphql").mock(
        return_value=httpx.Response(200, json=old_advisory_updated_recently)
    )
    source = {"id": "github-advisories", "url": "https://api.github.com/graphql"}
    since = datetime(2026, 8, 17, tzinfo=timezone.utc)
    until = datetime(2026, 8, 24, tzinfo=timezone.utc)

    items = fetch_github_advisories(source, since, until)
    assert items == []


@respx.mock
def test_fetch_github_advisories_raises_on_graphql_errors(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "test-token")
    respx.post("https://api.github.com/graphql").mock(
        return_value=httpx.Response(200, json={"errors": [{"message": "boom"}]})
    )
    source = {"id": "github-advisories", "url": "https://api.github.com/graphql"}
    since = datetime(2026, 8, 17, tzinfo=timezone.utc)
    until = datetime(2026, 8, 24, tzinfo=timezone.utc)

    try:
        fetch_github_advisories(source, since, until)
        assert False, "expected RuntimeError"
    except RuntimeError as exc:
        assert "boom" in str(exc)
