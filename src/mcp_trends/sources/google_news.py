from datetime import datetime, timezone, timedelta
from urllib.parse import quote_plus

import feedparser
import httpx

from mcp_trends.config import settings
from mcp_trends.models import SourceResult, TrendItem
from mcp_trends.sources._feed_utils import relevance_score, parse_date, fetch_feed

GOOGLE_NEWS_RSS = "https://news.google.com/rss/search?q={topic}&hl=en&gl=US&ceid=US:en"


async def search_google_news(topic: str, limit: int = 10) -> SourceResult:
    cutoff = datetime.now(timezone.utc) - timedelta(days=7)
    url = GOOGLE_NEWS_RSS.format(topic=quote_plus(topic))

    try:
        async with httpx.AsyncClient(timeout=settings.http_timeout, follow_redirects=True) as client:
            _, content = await fetch_feed(client, "Google News", url)

        if not content:
            return SourceResult(
                results=[], source="google_news", query=topic,
                error="Failed to fetch Google News RSS feed",
            )

        feed = feedparser.parse(content)
        items: list[TrendItem] = []

        for entry in feed.entries:
            pub_date = parse_date(entry)
            if pub_date and pub_date.tzinfo is None:
                pub_date = pub_date.replace(tzinfo=timezone.utc)
            if pub_date and pub_date < cutoff:
                continue

            title = entry.get("title", "")
            summary = entry.get("summary", "")
            link = entry.get("link", "")
            source_name = entry.get("source", {}).get("title", "Unknown")

            score = relevance_score(topic, title, summary, pub_date)
            if score < settings.rss_min_relevance_score:
                continue

            items.append(
                TrendItem(
                    title=title,
                    url=link,
                    source="google_news",
                    metadata={
                        "publication": source_name,
                        "published_date": pub_date.isoformat() if pub_date else "",
                        "summary": summary[:500],
                        "relevance_score": score,
                    },
                )
            )

        items.sort(key=lambda x: x.metadata.get("relevance_score", 0), reverse=True)
        return SourceResult(results=items[:limit], source="google_news", query=topic)

    except Exception as e:
        return SourceResult(results=[], source="google_news", query=topic, error=str(e))
