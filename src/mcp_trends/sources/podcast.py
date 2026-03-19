import asyncio
from datetime import datetime, timezone, timedelta

import feedparser
import httpx

from mcp_trends.config import settings
from mcp_trends.models import SourceResult, TrendItem
from mcp_trends.sources._feed_utils import relevance_score, parse_date, fetch_feed

ITUNES_SEARCH_URL = "https://itunes.apple.com/search"
MAX_SHOWS = 10


async def _discover_shows(client: httpx.AsyncClient, topic: str) -> list[dict]:
    resp = await client.get(
        ITUNES_SEARCH_URL,
        params={
            "term": topic,
            "media": "podcast",
            "limit": MAX_SHOWS,
        },
    )
    resp.raise_for_status()
    return resp.json().get("results", [])


async def _get_recent_episodes(
    client: httpx.AsyncClient,
    show: dict,
    topic: str,
    cutoff: datetime,
) -> list[TrendItem]:
    feed_url = show.get("feedUrl", "")
    if not feed_url:
        return []

    _, content = await fetch_feed(client, show.get("collectionName", ""), feed_url)
    if not content:
        return []

    feed = feedparser.parse(content)
    podcast_name = show.get("collectionName", "")
    artist = show.get("artistName", "")
    genre = show.get("primaryGenreName", "")

    show_score = relevance_score(topic, podcast_name, show.get("description", "") or "")
    itunes_baseline = max(show_score, 3.0)

    items = []
    for entry in feed.entries[:10]:
        pub_date = parse_date(entry)
        if pub_date and pub_date.tzinfo is None:
            pub_date = pub_date.replace(tzinfo=timezone.utc)
        if pub_date and pub_date < cutoff:
            continue

        title = entry.get("title", "")
        summary = entry.get("summary", "") or entry.get("subtitle", "") or ""
        episode_score = relevance_score(topic, title, summary, pub_date)
        score = round(max(episode_score, itunes_baseline) + episode_score, 2)

        items.append(
            TrendItem(
                title=title,
                url=entry.get("link", "") or show.get("trackViewUrl", ""),
                source="podcasts",
                metadata={
                    "podcast_name": podcast_name,
                    "artist": artist,
                    "genre": genre,
                    "description": summary[:300],
                    "published_date": pub_date.isoformat() if pub_date else "",
                    "relevance_score": score,
                    "episode_count": show.get("trackCount", 0),
                },
            )
        )

    return items


async def search_podcasts(topic: str, limit: int = 10) -> SourceResult:
    cutoff = datetime.now(timezone.utc) - timedelta(days=14)

    try:
        async with httpx.AsyncClient(
            timeout=settings.http_timeout, follow_redirects=True,
        ) as client:
            shows = await _discover_shows(client, topic)
            if not shows:
                return SourceResult(results=[], source="podcasts", query=topic)

            episode_lists = await asyncio.gather(
                *[_get_recent_episodes(client, show, topic, cutoff) for show in shows],
                return_exceptions=True,
            )

        items: list[TrendItem] = []
        for result in episode_lists:
            if isinstance(result, list):
                items.extend(result)

        items.sort(
            key=lambda x: x.metadata.get("relevance_score", 0), reverse=True,
        )

        seen: set[str] = set()
        deduped: list[TrendItem] = []
        for item in items:
            key = item.title.lower().strip()
            if key in seen:
                continue
            seen.add(key)
            deduped.append(item)

        return SourceResult(results=deduped[:limit], source="podcasts", query=topic)

    except Exception as e:
        return SourceResult(results=[], source="podcasts", query=topic, error=str(e))
