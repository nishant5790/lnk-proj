import asyncio
import json

from mcp.server.fastmcp import FastMCP

from mcp_trends.models import AggregatedTrends
from mcp_trends.sources.hackernews import search_hackernews
from mcp_trends.sources.youtube import search_youtube
from mcp_trends.sources.github import search_github
from mcp_trends.sources.linkedin import search_google_linkedin
from mcp_trends.sources.reddit import search_reddit
from mcp_trends.sources.rss import search_rss
from mcp_trends.sources.google_news import search_google_news
from mcp_trends.sources.podcast import search_podcasts
from mcp_trends.chains.summarizer import summarize_trends

mcp = FastMCP(
    "Trends MCP Server",
    instructions="Find trending topics across Hacker News, YouTube, GitHub, LinkedIn, Reddit, RSS feeds, Google News, and Podcasts",
)


@mcp.tool()
async def find_hackernews_trends(topic: str, limit: int = 10, period: str = "week") -> str:
    """Search Hacker News for trending stories about a topic, sorted newest-first.

    Args:
        topic: The topic to search for (e.g., "AI agents", "React", "startup funding")
        limit: Maximum number of results to return (default: 10)
        period: Time window — "week", "month", or "quarter" (default: "week")
    """
    result = await search_hackernews(topic, limit, period)
    return result.model_dump_json(indent=2)


@mcp.tool()
async def find_youtube_trends(topic: str, limit: int = 10) -> str:
    """Search YouTube for trending videos about a topic from the last 7 days.

    Args:
        topic: The topic to search for
        limit: Maximum number of results to return (default: 10)
    """
    result = await search_youtube(topic, limit)
    return result.model_dump_json(indent=2)


@mcp.tool()
async def find_github_trends(topic: str, limit: int = 10) -> str:
    """Search GitHub for trending repositories about a topic.

    Args:
        topic: The topic to search for
        limit: Maximum number of results to return (default: 10)
    """
    result = await search_github(topic, limit)
    return result.model_dump_json(indent=2)


@mcp.tool()
async def find_google_linkedin_trends(topic: str, limit: int = 10) -> str:
    """Search Google for trending LinkedIn posts and articles about a topic.

    Uses Gemini with Google Search grounding to find relevant LinkedIn content.

    Args:
        topic: The topic to search for
        limit: Maximum number of results to return (default: 10)
    """
    result = await search_google_linkedin(topic, limit)
    return result.model_dump_json(indent=2)


@mcp.tool()
async def find_reddit_trends(
    topic: str,
    limit: int = 10,
    period: str = "week",
    sort: str = "hot",
) -> str:
    """Search Reddit for trending discussions about a topic.

    Args:
        topic: The topic to search for
        limit: Maximum number of results to return (default: 10)
        period: Time window — "hour", "day", "week", "month", "year", "all" (default: "week")
        sort: Sort order — "relevance", "hot", "new", "top", "comments" (default: "hot")
    """
    result = await search_reddit(topic, limit, period, sort)
    return result.model_dump_json(indent=2)


@mcp.tool()
async def find_rss_trends(topic: str, limit: int = 10) -> str:
    """Search curated industry publications (TechCrunch, HubSpot, SaaStr, etc.) for articles about a topic.

    Args:
        topic: The topic to search for
        limit: Maximum number of results to return (default: 10)
    """
    result = await search_rss(topic, limit)
    return result.model_dump_json(indent=2)


@mcp.tool()
async def find_google_news_trends(topic: str, limit: int = 10) -> str:
    """Search Google News for trending articles about a topic from thousands of publications.

    Args:
        topic: The topic to search for
        limit: Maximum number of results to return (default: 10)
    """
    result = await search_google_news(topic, limit)
    return result.model_dump_json(indent=2)


@mcp.tool()
async def find_podcast_trends(topic: str, limit: int = 10) -> str:
    """Search Podcast Index for trending shows and episodes about a topic.

    Args:
        topic: The topic to search for
        limit: Maximum number of results to return (default: 10)
    """
    result = await search_podcasts(topic, limit)
    return result.model_dump_json(indent=2)


@mcp.tool()
async def aggregate_trends(topic: str, limit: int = 5) -> str:
    """Search ALL sources for trending content about a topic and provide an AI-generated summary.

    Queries Hacker News, YouTube, GitHub, LinkedIn, Reddit, RSS feeds, and Podcasts
    concurrently, then uses Gemini to analyze and summarize the top trends across all sources.

    Args:
        topic: The topic to search for
        limit: Maximum results per source (default: 5)
    """
    results = await asyncio.gather(
        search_hackernews(topic, limit),
        search_youtube(topic, limit),
        search_github(topic, limit),
        search_google_linkedin(topic, limit),
        search_reddit(topic, limit),
        search_rss(topic, limit),
        search_google_news(topic, limit),
        search_podcasts(topic, limit),
        return_exceptions=True,
    )

    source_names = ["hackernews", "youtube", "github", "google_linkedin", "reddit", "rss", "google_news", "podcasts"]
    source_results = {}

    for name, result in zip(source_names, results):
        if isinstance(result, Exception):
            from mcp_trends.models import SourceResult
            source_results[name] = SourceResult(
                results=[], source=name, query=topic, error=str(result)
            )
        else:
            source_results[name] = result

    summary = await summarize_trends(topic, source_results)

    aggregated = AggregatedTrends(
        raw_results=source_results,
        summary=summary,
        query=topic,
    )

    return aggregated.model_dump_json(indent=2)


if __name__ == "__main__":
    mcp.run(transport="stdio")
