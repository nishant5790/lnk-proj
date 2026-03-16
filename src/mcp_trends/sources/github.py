from datetime import datetime, timedelta

import httpx

from mcp_trends.config import settings
from mcp_trends.models import SourceResult, TrendItem


async def search_github(topic: str, limit: int = 10) -> SourceResult:
    url = "https://api.github.com/search/repositories"
    pushed_after = (datetime.utcnow() - timedelta(days=7)).strftime("%Y-%m-%d")
    query = f"{topic} pushed:>{pushed_after}"

    try:
        async with httpx.AsyncClient(timeout=settings.http_timeout) as client:
            response = await client.get(
                url,
                params={
                    "q": query,
                    "sort": "stars",
                    "order": "desc",
                    "per_page": limit * 3,
                },
                headers={"Accept": "application/vnd.github.v3+json"},
            )
            response.raise_for_status()
            data = response.json()

        now = datetime.utcnow()
        items = []
        for repo in data.get("items", []):
            created_str = repo.get("created_at", "")
            stars = repo.get("stargazers_count", 0)
            try:
                created_dt = datetime.fromisoformat(created_str.replace("Z", "+00:00"))
                age_days = max((now - created_dt.replace(tzinfo=None)).days, 1)
            except (ValueError, TypeError):
                age_days = 365
            stars_per_day = round(stars / age_days, 1)

            topics = repo.get("topics", [])
            license_info = repo.get("license") or {}

            items.append(
                TrendItem(
                    title=repo.get("full_name", ""),
                    url=repo.get("html_url", ""),
                    source="github",
                    metadata={
                        "description": repo.get("description", "") or "",
                        "stars": stars,
                        "forks": repo.get("forks_count", 0),
                        "open_issues": repo.get("open_issues_count", 0),
                        "stars_per_day": stars_per_day,
                        "language": repo.get("language", ""),
                        "topics": topics[:10],
                        "license": license_info.get("spdx_id", ""),
                        "created_at": created_str,
                        "updated_at": repo.get("updated_at", ""),
                    },
                )
            )

        items = [i for i in items if i.metadata.get("stars", 0) >= settings.github_min_stars]
        items.sort(key=lambda x: x.metadata.get("stars_per_day", 0), reverse=True)
        items = items[:limit]

        return SourceResult(results=items, source="github", query=topic)

    except Exception as e:
        return SourceResult(
            results=[], source="github", query=topic, error=str(e)
        )
