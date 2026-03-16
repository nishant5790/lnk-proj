from datetime import datetime, timedelta

import httpx

from mcp_trends.config import settings
from mcp_trends.models import SourceResult, TrendItem


async def search_youtube(topic: str, limit: int = 10) -> SourceResult:
    if not settings.youtube_api_key:
        return SourceResult(
            results=[], source="youtube", query=topic,
            error="YOUTUBE_API_KEY not configured",
        )

    base_url = "https://www.googleapis.com/youtube/v3"
    published_after = (datetime.utcnow() - timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%SZ")

    try:
        async with httpx.AsyncClient(timeout=settings.http_timeout) as client:
            search_resp = await client.get(
                f"{base_url}/search",
                params={
                    "part": "snippet",
                    "q": topic,
                    "type": "video",
                    "order": "viewCount",
                    "publishedAfter": published_after,
                    "maxResults": limit,
                    "key": settings.youtube_api_key,
                },
            )
            search_resp.raise_for_status()
            search_data = search_resp.json()

            video_ids = [
                item["id"]["videoId"]
                for item in search_data.get("items", [])
                if "videoId" in item.get("id", {})
            ]

            video_stats: dict[str, dict] = {}
            if video_ids:
                stats_resp = await client.get(
                    f"{base_url}/videos",
                    params={
                        "part": "statistics",
                        "id": ",".join(video_ids),
                        "key": settings.youtube_api_key,
                    },
                )
                stats_resp.raise_for_status()
                for item in stats_resp.json().get("items", []):
                    stats = item.get("statistics", {})
                    video_stats[item["id"]] = {
                        "view_count": int(stats.get("viewCount", 0)),
                        "like_count": int(stats.get("likeCount", 0)),
                        "comment_count": int(stats.get("commentCount", 0)),
                    }

        items = []
        for item in search_data.get("items", []):
            video_id = item.get("id", {}).get("videoId", "")
            snippet = item.get("snippet", {})
            stats = video_stats.get(video_id, {})
            views = stats.get("view_count", 0)
            likes = stats.get("like_count", 0)
            like_ratio = round(likes / max(views, 1) * 100, 2)

            items.append(
                TrendItem(
                    title=snippet.get("title", ""),
                    url=f"https://www.youtube.com/watch?v={video_id}",
                    source="youtube",
                    metadata={
                        "channel": snippet.get("channelTitle", ""),
                        "view_count": views,
                        "like_count": likes,
                        "comment_count": stats.get("comment_count", 0),
                        "like_ratio_pct": like_ratio,
                        "published_at": snippet.get("publishedAt", ""),
                        "description": snippet.get("description", ""),
                    },
                )
            )

        items = [i for i in items if i.metadata.get("view_count", 0) >= settings.youtube_min_views]
        items.sort(key=lambda x: x.metadata.get("like_ratio_pct", 0), reverse=True)

        return SourceResult(results=items, source="youtube", query=topic)

    except Exception as e:
        return SourceResult(
            results=[], source="youtube", query=topic, error=str(e)
        )
