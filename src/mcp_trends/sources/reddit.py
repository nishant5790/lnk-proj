import asyncio
from datetime import datetime, timezone

import httpx

from mcp_trends.config import settings
from mcp_trends.models import SourceResult, TrendItem

SEARCH_URL = "https://www.reddit.com/search.json"
MAX_RETRIES = 3
BASE_DELAY = 1.0


async def _reddit_get(client: httpx.AsyncClient, url: str, params: dict) -> httpx.Response:
    for attempt in range(MAX_RETRIES):
        resp = await client.get(url, params=params)
        if resp.status_code != 429:
            resp.raise_for_status()
            return resp
        retry_after = float(resp.headers.get("Retry-After", BASE_DELAY * (2 ** attempt)))
        await asyncio.sleep(retry_after)
    raise httpx.HTTPStatusError(
        "Rate limit exceeded after retries",
        request=resp.request,
        response=resp,
    )


async def search_reddit(topic: str, limit: int = 10) -> SourceResult:
    try:
        async with httpx.AsyncClient(
            timeout=settings.http_timeout,
            headers={"User-Agent": settings.reddit_user_agent},
        ) as client:
            resp = await _reddit_get(client, SEARCH_URL, {
                "q": topic,
                "sort": "hot",
                "t": "week",
                "limit": min(limit * 3, 100),
                "type": "link",
            })
            data = resp.json()

        items = []
        for post in data.get("data", {}).get("children", []):
            d = post.get("data", {})
            score = d.get("score", 0)
            if score < settings.reddit_min_score:
                continue

            created = datetime.fromtimestamp(d.get("created_utc", 0), tz=timezone.utc)
            items.append(
                TrendItem(
                    title=d.get("title", ""),
                    url=f"https://www.reddit.com{d.get('permalink', '')}",
                    source="reddit",
                    metadata={
                        "score": score,
                        "num_comments": d.get("num_comments", 0),
                        "upvote_ratio": d.get("upvote_ratio", 0),
                        "subreddit": d.get("subreddit", ""),
                        "author": d.get("author", ""),
                        "created_utc": created.isoformat(),
                        "selftext": (d.get("selftext", "") or "")[:300],
                    },
                )
            )

        items.sort(
            key=lambda x: x.metadata.get("score", 0) * x.metadata.get("upvote_ratio", 0),
            reverse=True,
        )
        return SourceResult(results=items[:limit], source="reddit", query=topic)

    except Exception as e:
        return SourceResult(results=[], source="reddit", query=topic, error=str(e))
