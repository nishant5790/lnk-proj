from datetime import datetime, timedelta, timezone
from typing import Literal

import httpx

from mcp_trends.config import settings
from mcp_trends.models import SourceResult, TrendItem

Period = Literal["week", "month", "quarter"]

PERIOD_DAYS: dict[Period, int] = {
    "week": 7,
    "month": 30,
    "quarter": 90,
}


async def search_hackernews(
    topic: str, limit: int = 10, period: Period = "week"
) -> SourceResult:
    items = await _fetch_window(topic, limit, period)
    quality = [i for i in items if i.metadata.get("points", 0) >= settings.hackernews_min_points]
    results = quality[:limit] if quality else items[:limit]
    return SourceResult(results=results, source="hackernews", query=topic)


async def _fetch_window(topic: str, limit: int, period: Period) -> list[TrendItem]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=PERIOD_DAYS[period])
    cutoff_ts = int(cutoff.timestamp())

    url = "https://hn.algolia.com/api/v1/search_by_date"
    params = {
        "query": topic,
        "tags": "story",
        "hitsPerPage": max(limit * 3, 30),
        "numericFilters": f"created_at_i>{cutoff_ts}",
    }

    try:
        async with httpx.AsyncClient(timeout=settings.http_timeout) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
    except Exception:
        return []

    seen_urls: set[str] = set()
    items = []
    for hit in data.get("hits", []):
        points = hit.get("points", 0) or 0
        num_comments = hit.get("num_comments", 0) or 0
        object_id = hit.get("objectID", "")
        url = hit.get("url") or f"https://news.ycombinator.com/item?id={object_id}"

        if url in seen_urls:
            continue
        seen_urls.add(url)

        engagement_ratio = round(num_comments / max(points, 1), 2)

        items.append(
            TrendItem(
                title=hit.get("title", ""),
                url=url,
                source="hackernews",
                metadata={
                    "points": points,
                    "num_comments": num_comments,
                    "engagement_ratio": engagement_ratio,
                    "discussion_url": f"https://news.ycombinator.com/item?id={object_id}",
                    "author": hit.get("author", ""),
                    "created_at": hit.get("created_at", ""),
                },
            )
        )

    items.sort(key=lambda x: x.metadata.get("points", 0), reverse=True)
    return items
