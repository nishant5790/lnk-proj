import asyncio
import hashlib
import time

import httpx

from mcp_trends.config import settings
from mcp_trends.models import SourceResult, TrendItem

BASE_URL = "https://api.podcastindex.org/api/1.0"


def _auth_headers() -> dict[str, str]:
    epoch = str(int(time.time()))
    data = settings.podcast_index_api_key + settings.podcast_index_api_secret + epoch
    sha1 = hashlib.sha1(data.encode("utf-8")).hexdigest()
    return {
        "User-Agent": "mcp-trends/0.1",
        "X-Auth-Key": settings.podcast_index_api_key,
        "X-Auth-Date": epoch,
        "Authorization": sha1,
    }


async def _search_episodes(client: httpx.AsyncClient, topic: str, limit: int) -> list[TrendItem]:
    resp = await client.get(
        f"{BASE_URL}/search/byterm",
        params={"q": topic, "max": limit, "fulltext": "true"},
        headers=_auth_headers(),
    )
    resp.raise_for_status()
    data = resp.json()

    items = []
    for feed in data.get("feeds", []):
        items.append(
            TrendItem(
                title=feed.get("title", ""),
                url=feed.get("url", "") or feed.get("link", ""),
                source="podcasts",
                metadata={
                    "podcast_name": feed.get("title", ""),
                    "description": (feed.get("description", "") or "")[:300],
                    "author": feed.get("author", ""),
                    "categories": list((feed.get("categories") or {}).values())[:5],
                    "type": "episode_match",
                    "language": feed.get("language", ""),
                },
            )
        )
    return items


async def _trending_podcasts(client: httpx.AsyncClient, topic: str, limit: int) -> list[TrendItem]:
    resp = await client.get(
        f"{BASE_URL}/podcasts/trending",
        params={"max": 20, "lang": "en"},
        headers=_auth_headers(),
    )
    resp.raise_for_status()
    data = resp.json()

    topic_lower = topic.lower()
    items = []
    for feed in data.get("feeds", []):
        title = feed.get("title", "")
        desc = feed.get("description", "") or ""
        if topic_lower not in title.lower() and topic_lower not in desc.lower():
            continue

        items.append(
            TrendItem(
                title=title,
                url=feed.get("url", "") or feed.get("link", ""),
                source="podcasts",
                metadata={
                    "podcast_name": title,
                    "description": desc[:300],
                    "author": feed.get("author", ""),
                    "trend_score": feed.get("trendScore", 0),
                    "type": "trending_show",
                    "language": feed.get("language", ""),
                },
            )
        )
    return items


async def search_podcasts(topic: str, limit: int = 10) -> SourceResult:
    if not settings.podcast_index_api_key or not settings.podcast_index_api_secret:
        return SourceResult(
            results=[], source="podcasts", query=topic,
            error="PODCAST_INDEX_API_KEY / PODCAST_INDEX_API_SECRET not configured",
        )

    try:
        async with httpx.AsyncClient(timeout=settings.http_timeout) as client:
            episodes, trending = await asyncio.gather(
                _search_episodes(client, topic, limit),
                _trending_podcasts(client, topic, limit),
            )

        seen_titles: set[str] = set()
        merged: list[TrendItem] = []
        for item in trending + episodes:
            key = item.title.lower().strip()
            if key in seen_titles:
                continue
            seen_titles.add(key)
            merged.append(item)

        return SourceResult(results=merged[:limit], source="podcasts", query=topic)

    except Exception as e:
        return SourceResult(results=[], source="podcasts", query=topic, error=str(e))
