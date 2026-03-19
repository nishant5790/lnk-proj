import json
import re
from datetime import datetime

from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI

from mcp_trends.config import settings
from mcp_trends.models import ContentAngle, SourceResult, TrendSummary


SUMMARIZER_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "You are a LinkedIn content strategist who analyzes trending data from 8 sources "
            "to find high-engagement post opportunities.\n\n"
            "Sources and what they signal:\n"
            "- hackernews: Developer/founder sentiment, technical depth\n"
            "- youtube: Visual/educational trends, broad audience interest\n"
            "- github: What builders are actually creating, open-source momentum. "
            "Pay special attention to the FASTEST-GROWING REPOS section — high stars/day on "
            "young repos is one of the strongest trend signals in tech.\n"
            "- google_linkedin: What's already performing on LinkedIn\n"
            "- reddit: Raw community pain points, unfiltered debates, real opinions\n"
            "- rss: Curated industry publications (TechCrunch, SaaStr, etc.)\n"
            "- google_news: Breaking news coverage across mainstream media\n"
            "- podcasts: What thought leaders are discussing — these topics often hit "
            "LinkedIn 2-4 weeks later, making them excellent for early-mover content\n\n"
            "CRITICAL RULE: Before generating trends, scan ALL sources for overlapping stories — "
            "any topic, narrative, or entity appearing in 2 or more sources is a CROSS-PLATFORM "
            "SIGNAL and MUST be auto-promoted to the top of top_trends. The more sources it "
            "appears in, the higher it ranks. A story in 4 sources always outranks one in 2.\n\n"
            "Your goal is to identify trends that would make compelling LinkedIn posts — "
            "contrarian takes, surprising data, practical insights, or emerging narratives "
            "that spark conversation. Podcast signals are especially valuable for spotting "
            "trends before they go mainstream.",
        ),
        (
            "human",
            "Topic: {topic}\n\n"
            "Raw trending data from multiple sources:\n{raw_data}\n\n"
            "Analyze this data and provide:\n\n"
            "STEP 0 (do this first): Scan every item across ALL sources. Identify stories, "
            "themes, or entities that appear in 2+ different sources. These are your strongest "
            "signals — rank them by number of source appearances.\n\n"
            "1. **top_trends** — Top 5 trending themes (short strings). Cross-platform stories "
            "(appearing in 2+ sources) MUST be ranked first, ordered by source count.\n\n"
            "2. **content_angles** — For each trend, provide a LinkedIn content angle:\n"
            '   - "hook": An attention-grabbing opening line for a LinkedIn post (the kind that stops the scroll)\n'
            '   - "angle": The specific take or insight to develop in the post (2-3 sentences)\n'
            '   - "supporting_sources": Which sources back this up (e.g. ["hackernews", "github", "podcasts"])\n\n'
            "3. **analysis** — A 2-3 paragraph analysis covering:\n"
            "   - What narratives are forming and why they resonate\n"
            "   - Which angles have the strongest cross-platform engagement signals\n"
            "   - Any contrarian or surprising angles that could drive high engagement\n"
            "   - Any early signals from podcasts or niche sources that haven't hit mainstream yet\n\n"
            "Respond in this exact JSON format:\n"
            "{{\n"
            '  "top_trends": ["trend1", "trend2", ...],\n'
            '  "content_angles": [\n'
            '    {{"hook": "...", "angle": "...", "supporting_sources": ["..."]}}\n'
            "  ],\n"
            '  "analysis": "..."\n'
            "}}",
        ),
    ]
)


def _extract_github_velocity(source_results: dict[str, SourceResult]) -> str:
    github = source_results.get("github")
    if not github or github.error or not github.results:
        return ""

    top_repos = sorted(
        github.results,
        key=lambda x: x.metadata.get("stars_per_day", 0),
        reverse=True,
    )[:3]

    if not top_repos or top_repos[0].metadata.get("stars_per_day", 0) < 1:
        return ""

    lines = ["## FASTEST-GROWING GITHUB REPOS THIS WEEK (primary trend signal)"]
    for repo in top_repos:
        m = repo.metadata
        lines.append(
            f"- {repo.title}: {m.get('stars_per_day', 0)} stars/day, "
            f"{m.get('stars', 0)} total stars, "
            f"language={m.get('language', 'N/A')}, "
            f"description: {m.get('description', '')}"
        )
    lines.append("")

    return "\n".join(lines) + "\n"


def _extract_json(text: str) -> dict:
    """Extract a JSON object from LLM output that may contain markdown fences."""
    text = text.strip()
    first_brace = text.find("{")
    last_brace = text.rfind("}")
    if first_brace == -1 or last_brace == -1:
        raise ValueError("No JSON object found")
    return json.loads(text[first_brace : last_brace + 1], strict=False)


async def summarize_trends(
    topic: str, source_results: dict[str, SourceResult]
) -> TrendSummary:
    if not settings.google_api_key:
        return TrendSummary(
            top_trends=["Error: GOOGLE_API_KEY not configured"],
            analysis="Cannot generate summary without Google API key.",
        )

    highlighted_signals = _extract_github_velocity(source_results)

    raw_data_parts = []
    for source_name, result in source_results.items():
        if result.error:
            raw_data_parts.append(f"## {source_name} (ERROR: {result.error})")
            continue
        items_text = json.dumps(
            [item.model_dump() for item in result.results[:5]], indent=2
        )
        raw_data_parts.append(f"## {source_name}\n{items_text}")

    raw_data = highlighted_signals + "\n\n".join(raw_data_parts)

    llm = ChatGoogleGenerativeAI(
        model="gemini-2.0-flash",
        google_api_key=settings.google_api_key,
        temperature=0.3,
    )

    chain = SUMMARIZER_PROMPT | llm

    try:
        response = await chain.ainvoke({"topic": topic, "raw_data": raw_data})
        content = response.content if isinstance(response.content, str) else str(response.content)

        parsed = _extract_json(content)
        angles = [
            ContentAngle(**a) for a in parsed.get("content_angles", [])
            if isinstance(a, dict)
        ]
        return TrendSummary(
            top_trends=parsed.get("top_trends", []),
            content_angles=angles,
            analysis=parsed.get("analysis", ""),
        )

    except (json.JSONDecodeError, KeyError, ValueError):
        return TrendSummary(
            top_trends=[],
            analysis=content if "content" in dir() else "Failed to parse summary",
        )
    except Exception as e:
        return TrendSummary(
            top_trends=["Error generating summary"],
            analysis=str(e),
        )
