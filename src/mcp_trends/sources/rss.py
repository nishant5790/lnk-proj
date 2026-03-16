import asyncio
import re
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime

import feedparser
import httpx

from mcp_trends.config import settings
from mcp_trends.models import SourceResult, TrendItem

DEFAULT_FEEDS: dict[str, str] = {
    "TechCrunch": "https://techcrunch.com/feed/",
    "HubSpot": "https://blog.hubspot.com/rss.xml",
    "SaaStr": "https://www.saastr.com/feed/",
    "First Round Review": "https://review.firstround.com/feed.xml",
    "Hacker Noon": "https://hackernoon.com/feed",
    "The Verge": "https://www.theverge.com/rss/index.xml",
    "Ars Technica": "https://feeds.arstechnica.com/arstechnica/index",
}

_WORD_RE = re.compile(r"\w+", re.UNICODE)


def _relevance_score(topic: str, title: str, summary: str) -> float:
    topic_words = set(w.lower() for w in _WORD_RE.findall(topic))
    if not topic_words:
        return 0.0
    text_words = _WORD_RE.findall(f"{title} {summary}".lower())
    if not text_words:
        return 0.0
    matches = sum(1 for w in text_words if w in topic_words)
    return round(matches / len(topic_words), 2)


def _parse_date(entry: dict) -> datetime | None:
    for field in ("published", "updated"):
        raw = entry.get(field)
        if not raw:
            continue
        try:
            return parsedate_to_datetime(raw)
        except Exception:
            pass
    return None


async def _fetch_feed(client: httpx.AsyncClient, name: str, url: str) -> tuple[str, str]:
    try:
        resp = await client.get(url)
        resp.raise_for_status()
        return name, resp.text
    except Exception:
        return name, ""


async def search_rss(topic: str, limit: int = 10) -> SourceResult:
    cutoff = datetime.now(timezone.utc) - timedelta(days=7)

    try:
        async with httpx.AsyncClient(timeout=settings.http_timeout) as client:
            tasks = [_fetch_feed(client, name, url) for name, url in DEFAULT_FEEDS.items()]
            raw_feeds = await asyncio.gather(*tasks)

        items: list[TrendItem] = []
        for pub_name, content in raw_feeds:
            if not content:
                continue
            feed = feedparser.parse(content)
            for entry in feed.entries:
                pub_date = _parse_date(entry)
                if pub_date and pub_date.tzinfo is None:
                    pub_date = pub_date.replace(tzinfo=timezone.utc)
                if pub_date and pub_date < cutoff:
                    continue

                title = entry.get("title", "")
                summary = entry.get("summary", "")
                score = _relevance_score(topic, title, summary)
                if score < settings.rss_min_relevance_score:
                    continue

                categories = [t.get("term", "") for t in entry.get("tags", [])]

                items.append(
                    TrendItem(
                        title=title,
                        url=entry.get("link", ""),
                        source="rss",
                        metadata={
                            "publication": pub_name,
                            "published_date": pub_date.isoformat() if pub_date else "",
                            "summary": summary[:500],
                            "relevance_score": score,
                            "categories": categories[:5],
                        },
                    )
                )

        items.sort(key=lambda x: x.metadata.get("relevance_score", 0), reverse=True)
        return SourceResult(results=items[:limit], source="rss", query=topic)

    except Exception as e:
        return SourceResult(results=[], source="rss", query=topic, error=str(e))
