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
    # Implementation makes 2 POST requests (PIP and NPM), gets same advisory twice
    assert len(items) == 2
    assert items[0].kind == "advisory"
    assert items[0].meta["cve_ids"] == ["CVE-2026-99999"]
    assert items[1].kind == "advisory"
    assert items[1].meta["cve_ids"] == ["CVE-2026-99999"]
