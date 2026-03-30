import re
from datetime import datetime, timezone, timedelta

import feedparser
import httpx

from mcp_trends.config import settings
from mcp_trends.models import SourceResult, TrendItem
from mcp_trends.sources._feed_utils import relevance_score

ARXIV_API_URL = "https://export.arxiv.org/api/query"
FALLBACK_MIN_RESULTS = 3
PRIMARY_WINDOW_DAYS = 7
FALLBACK_WINDOW_DAYS = 30

_VERSION_RE = re.compile(r"v(\d+)$")


async def search_arxiv(topic: str, limit: int = 10) -> SourceResult:
    try:
        items = await _fetch_and_parse(topic, limit, PRIMARY_WINDOW_DAYS)

        if len(items) < FALLBACK_MIN_RESULTS:
            items = await _fetch_and_parse(topic, limit, FALLBACK_WINDOW_DAYS)

        items.sort(key=lambda x: x.metadata.get("relevance_score", 0), reverse=True)
        return SourceResult(results=items[:limit], source="arxiv", query=topic)

    except Exception as e:
        return SourceResult(results=[], source="arxiv", query=topic, error=str(e))


async def _fetch_and_parse(topic: str, limit: int, window_days: int) -> list[TrendItem]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=window_days)

    params = {
        "search_query": f"all:{topic}",
        "sortBy": "submittedDate",
        "sortOrder": "descending",
        "start": 0,
        "max_results": max(limit * 3, 30),
    }

    async with httpx.AsyncClient(timeout=settings.http_timeout) as client:
        resp = await client.get(ARXIV_API_URL, params=params)
        resp.raise_for_status()

    feed = feedparser.parse(resp.text)
    items: list[TrendItem] = []

    for entry in feed.entries:
        published = _parse_datetime(entry.get("published", ""))
        updated = _parse_datetime(entry.get("updated", ""))
        pub_date = published or updated
        if pub_date and pub_date < cutoff:
            continue

        title = entry.get("title", "").replace("\n", " ").strip()
        abstract = entry.get("summary", "").replace("\n", " ").strip()

        score = relevance_score(topic, title, abstract, pub_date)
        if score < settings.rss_min_relevance_score:
            continue

        authors_raw = entry.get("authors", [])
        author_names = [a.get("name", "") for a in authors_raw if a.get("name")]
        author_count = len(author_names)
        authors_display = author_names[:5]
        if author_count > 5:
            authors_display.append(f"... +{author_count - 5} more")

        categories = [t.get("term", "") for t in entry.get("tags", []) if t.get("term")]

        entry_id = entry.get("id", "")
        abs_url = entry_id
        pdf_url = entry_id.replace("/abs/", "/pdf/")

        version_match = _VERSION_RE.search(entry_id)
        num_versions = int(version_match.group(1)) if version_match else 1

        items.append(
            TrendItem(
                title=title,
                url=abs_url,
                source="arxiv",
                metadata={
                    "authors": authors_display,
                    "author_count": author_count,
                    "abstract": abstract[:500],
                    "categories": categories,
                    "pdf_url": pdf_url,
                    "published_date": pub_date.isoformat() if pub_date else "",
                    "updated_date": updated.isoformat() if updated else "",
                    "num_versions": num_versions,
                    "relevance_score": score,
                },
            )
        )

    return items


def _parse_datetime(raw: str) -> datetime | None:
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None
