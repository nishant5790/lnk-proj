import json

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage

from mcp_trends.config import settings
from mcp_trends.models import SourceResult, TrendItem


async def search_google_linkedin(topic: str, limit: int = 10) -> SourceResult:
    if not settings.google_api_key:
        return SourceResult(
            results=[],
            source="google_linkedin",
            query=topic,
            error="GOOGLE_API_KEY not configured",
        )

    try:
        llm = ChatGoogleGenerativeAI(
            model="gemini-2.0-flash",
            google_api_key=settings.google_api_key,
            temperature=0,
        )

        prompt = (
            f"Search Google for: {topic} site:linkedin.com\n\n"
            f"Find the top {limit} most recent and trending LinkedIn posts or articles about '{topic}'. "
            "Focus on posts from the last 7 days that have high engagement.\n\n"
            "Return ONLY a JSON array (no markdown fences) with this exact structure:\n"
            "[\n"
            "  {{\n"
            '    "title": "Post headline",\n'
            '    "url": "https://linkedin.com/...",\n'
            '    "author": "Author Name",\n'
            '    "engagement_type": "opinion|data-driven|how-to|contrarian|storytelling|news-reaction",\n'
            '    "key_takeaway": "The single most interesting or surprising claim from this post",\n'
            '    "summary": "1-2 sentence summary"\n'
            "  }}\n"
            "]\n\n"
            "If a URL is unavailable, use an empty string. Always return valid JSON."
        )

        response = await llm.ainvoke(
            [HumanMessage(content=prompt)],
            tools=[{"google_search": {}}],
        )

        raw = response.content
        if isinstance(raw, list):
            content = "\n".join(str(part) for part in raw)
        else:
            content = str(raw)

        items = _parse_linkedin_results(content, topic)

        if not items:
            items.append(
                TrendItem(
                    title=f"LinkedIn trends: {topic}",
                    url=f"https://www.linkedin.com/search/results/content/?keywords={topic}",
                    source="google_linkedin",
                    metadata={"raw_response": content},
                )
            )

        return SourceResult(results=items, source="google_linkedin", query=topic)

    except Exception as e:
        return SourceResult(
            results=[], source="google_linkedin", query=topic, error=str(e)
        )


def _parse_linkedin_results(content: str, topic: str) -> list[TrendItem]:
    """Parse Gemini's response into structured TrendItems."""
    text = content.strip()
    if isinstance(text, str) and text.startswith("["):
        pass
    else:
        start = text.find("[")
        end = text.rfind("]")
        if start == -1 or end == -1:
            return []
        text = text[start : end + 1]

    try:
        entries = json.loads(text, strict=False)
    except json.JSONDecodeError:
        return []

    if not isinstance(entries, list):
        return []

    items = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        title = entry.get("title", "").strip()
        if not title:
            continue
        items.append(
            TrendItem(
                title=title,
                url=entry.get("url", "") or f"https://www.linkedin.com/search/results/content/?keywords={topic}",
                source="google_linkedin",
                metadata={
                    "author": entry.get("author", ""),
                    "engagement_type": entry.get("engagement_type", ""),
                    "key_takeaway": entry.get("key_takeaway", ""),
                    "summary": entry.get("summary", ""),
                },
            )
        )

    return items
