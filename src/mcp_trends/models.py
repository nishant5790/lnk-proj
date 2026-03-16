from datetime import datetime

from pydantic import BaseModel, Field


class TrendItem(BaseModel):
    title: str
    url: str
    source: str
    metadata: dict = Field(default_factory=dict)


class SourceResult(BaseModel):
    results: list[TrendItem]
    source: str
    query: str
    fetched_at: datetime = Field(default_factory=datetime.utcnow)
    error: str | None = None


class ContentAngle(BaseModel):
    hook: str
    angle: str
    supporting_sources: list[str] = Field(default_factory=list)


class TrendSummary(BaseModel):
    top_trends: list[str]
    content_angles: list[ContentAngle] = Field(default_factory=list)
    analysis: str
    generated_at: datetime = Field(default_factory=datetime.utcnow)


class AggregatedTrends(BaseModel):
    raw_results: dict[str, SourceResult]
    summary: TrendSummary | None = None
    query: str
