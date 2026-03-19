import asyncio
from datetime import datetime, timezone, timedelta

import feedparser
import httpx

from mcp_trends.config import settings
from mcp_trends.models import SourceResult, TrendItem
from mcp_trends.sources._feed_utils import relevance_score, parse_date, fetch_feed

CURATED_FEEDS: dict[str, str] = {
    "TechCrunch": "https://techcrunch.com/feed/",
    "HubSpot": "https://blog.hubspot.com/rss.xml",
    "SaaStr": "https://www.saastr.com/feed/",
    "First Round Review": "https://review.firstround.com/feed.xml",
    "Hacker Noon": "https://hackernoon.com/feed",
    "The Verge": "https://www.theverge.com/rss/index.xml",
    "Ars Technica": "https://feeds.arstechnica.com/arstechnica/index",
}


async def search_rss(topic: str, limit: int = 10) -> SourceResult:
    cutoff = datetime.now(timezone.utc) - timedelta(days=7)

    try:
        async with httpx.AsyncClient(timeout=settings.http_timeout) as client:
            tasks = [fetch_feed(client, name, url) for name, url in CURATED_FEEDS.items()]
            raw_feeds = await asyncio.gather(*tasks)

        items: list[TrendItem] = []
        for pub_name, content in raw_feeds:
            if not content:
                continue
            feed = feedparser.parse(content)
            for entry in feed.entries:
                pub_date = parse_date(entry)
                if pub_date and pub_date.tzinfo is None:
                    pub_date = pub_date.replace(tzinfo=timezone.utc)
                if pub_date and pub_date < cutoff:
                    continue

                title = entry.get("title", "")
                summary = entry.get("summary", "")
                score = relevance_score(topic, title, summary, pub_date)
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
