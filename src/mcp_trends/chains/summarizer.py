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
            "You are a LinkedIn content strategist who analyzes trending data to find "
            "high-engagement post opportunities. Your goal is to identify trends that "
            "would make compelling LinkedIn posts — contrarian takes, surprising data, "
            "practical insights, or emerging narratives that spark conversation.",
        ),
        (
            "human",
            "Topic: {topic}\n\n"
            "Raw trending data from multiple sources:\n{raw_data}\n\n"
            "Analyze this data and provide:\n\n"
            "1. **top_trends** — Top 5 trending themes (short strings)\n\n"
            "2. **content_angles** — For each trend, provide a LinkedIn content angle:\n"
            '   - "hook": An attention-grabbing opening line for a LinkedIn post (the kind that stops the scroll)\n'
            '   - "angle": The specific take or insight to develop in the post (2-3 sentences)\n'
            '   - "supporting_sources": Which sources back this up (e.g. ["hackernews", "github"])\n\n'
            "3. **analysis** — A 2-3 paragraph analysis covering:\n"
            "   - What narratives are forming and why they resonate\n"
            "   - Which angles have the strongest cross-platform engagement signals\n"
            "   - Any contrarian or surprising angles that could drive high engagement\n\n"
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

    raw_data_parts = []
    for source_name, result in source_results.items():
        if result.error:
            raw_data_parts.append(f"## {source_name} (ERROR: {result.error})")
            continue
        items_text = json.dumps(
            [item.model_dump() for item in result.results[:5]], indent=2
        )
        raw_data_parts.append(f"## {source_name}\n{items_text}")

    raw_data = "\n\n".join(raw_data_parts)

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
