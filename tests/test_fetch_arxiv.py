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
