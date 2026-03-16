from datetime import datetime, timedelta
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

ESCALATION_ORDER: list[Period] = ["week", "month", "quarter"]


async def search_hackernews(
    topic: str, limit: int = 10, period: Period = "week"
) -> SourceResult:
    start_idx = ESCALATION_ORDER.index(period)

    for window in ESCALATION_ORDER[start_idx:]:
        items = await _fetch_window(topic, limit, window)
        quality = [i for i in items if i.metadata.get("points", 0) >= settings.hackernews_min_points]
        if len(quality) >= min(limit, 3):
            items = quality[:limit]
            items.sort(key=lambda x: x.metadata.get("created_at", ""), reverse=True)
            return SourceResult(results=items, source="hackernews", query=topic)

    items.sort(key=lambda x: x.metadata.get("created_at", ""), reverse=True)
    return SourceResult(results=items[:limit], source="hackernews", query=topic)


async def _fetch_window(topic: str, limit: int, period: Period) -> list[TrendItem]:
    cutoff = datetime.utcnow() - timedelta(days=PERIOD_DAYS[period])
    cutoff_ts = int(cutoff.timestamp())

    url = "https://hn.algolia.com/api/v1/search"
    params = {
        "query": topic,
        "tags": "story",
        "hitsPerPage": max(limit * 2, 20),
        "numericFilters": f"created_at_i>{cutoff_ts}",
    }

    try:
        async with httpx.AsyncClient(timeout=settings.http_timeout) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
    except Exception:
        return []

    items = []
    for hit in data.get("hits", []):
        points = hit.get("points", 0) or 0
        num_comments = hit.get("num_comments", 0) or 0
        engagement_ratio = round(num_comments / max(points, 1), 2)
        object_id = hit.get("objectID", "")

        items.append(
            TrendItem(
                title=hit.get("title", ""),
                url=hit.get("url") or f"https://news.ycombinator.com/item?id={object_id}",
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

    items.sort(key=lambda x: x.metadata.get("num_comments", 0), reverse=True)
    return items
