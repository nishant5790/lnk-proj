from __future__ import annotations

import asyncio
from typing import Literal

import uvicorn
from fastapi import FastAPI, Query
from pydantic import BaseModel, Field

from mcp_trends.chains.summarizer import summarize_trends
from mcp_trends.config import settings
from mcp_trends.models import AggregatedTrends, SourceResult
from mcp_trends.sources.github import search_github
from mcp_trends.sources.google import search_google_linkedin
from mcp_trends.sources.hackernews import search_hackernews
from mcp_trends.sources.youtube import search_youtube

Period = Literal["week", "month", "quarter"]

app = FastAPI(
    title="MCP Trends API",
    description="REST API wrapper for the MCP Trends server",
    version="0.1.0",
)


class TrendRequest(BaseModel):
    topic: str = Field(..., min_length=1, description="Topic to search trends for")
    limit: int = Field(default=10, ge=1, le=50, description="Maximum results to fetch")
    period: Period = Field(default="week", description="Time period used for Hacker News")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/")
async def root() -> dict[str, object]:
    return {
        "service": "mcp-trends-api",
        "version": "0.1.0",
        "docs": "/docs",
        "endpoints": [
            "/trends/hackernews",
            "/trends/youtube",
            "/trends/github",
            "/trends/google-linkedin",
            "/trends/aggregate",
        ],
    }


@app.post("/trends/hackernews", response_model=SourceResult)
async def hackernews_trends(payload: TrendRequest) -> SourceResult:
    return await search_hackernews(payload.topic, payload.limit, payload.period)


@app.post("/trends/youtube", response_model=SourceResult)
async def youtube_trends(payload: TrendRequest) -> SourceResult:
    return await search_youtube(payload.topic, payload.limit)


@app.post("/trends/github", response_model=SourceResult)
async def github_trends(payload: TrendRequest) -> SourceResult:
    return await search_github(payload.topic, payload.limit)


@app.post("/trends/google-linkedin", response_model=SourceResult)
async def google_linkedin_trends(payload: TrendRequest) -> SourceResult:
    return await search_google_linkedin(payload.topic, payload.limit)


@app.post("/trends/aggregate", response_model=AggregatedTrends)
async def aggregate_trends(payload: TrendRequest) -> AggregatedTrends:
    results = await asyncio.gather(
        search_hackernews(payload.topic, payload.limit, payload.period),
        search_youtube(payload.topic, payload.limit),
        search_github(payload.topic, payload.limit),
        search_google_linkedin(payload.topic, payload.limit),
        return_exceptions=True,
    )

    source_names = ["hackernews", "youtube", "github", "google_linkedin"]
    source_results: dict[str, SourceResult] = {}

    for name, result in zip(source_names, results):
        if isinstance(result, Exception):
            source_results[name] = SourceResult(
                results=[],
                source=name,
                query=payload.topic,
                error=str(result),
            )
        else:
            source_results[name] = result

    summary = await summarize_trends(payload.topic, source_results)
    return AggregatedTrends(raw_results=source_results, summary=summary, query=payload.topic)


@app.get("/trends/{source}", response_model=SourceResult)
async def trends_by_source(
    source: Literal["hackernews", "youtube", "github", "google-linkedin"],
    topic: str = Query(..., min_length=1),
    limit: int = Query(10, ge=1, le=50),
    period: Period = Query("week"),
) -> SourceResult:
    if source == "hackernews":
        return await search_hackernews(topic, limit, period)
    if source == "youtube":
        return await search_youtube(topic, limit)
    if source == "github":
        return await search_github(topic, limit)
    return await search_google_linkedin(topic, limit)


def main() -> None:
    uvicorn.run(
        "mcp_trends.api:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=False,
    )


if __name__ == "__main__":
    main()
