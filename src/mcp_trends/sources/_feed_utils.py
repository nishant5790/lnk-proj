import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

import httpx

_WORD_RE = re.compile(r"\w+", re.UNICODE)


def relevance_score(
    topic: str, title: str, summary: str, pub_date: datetime | None = None,
) -> float:
    topic_lower = topic.lower()
    topic_words = set(w.lower() for w in _WORD_RE.findall(topic))
    if not topic_words:
        return 0.0

    text = f"{title} {summary}".lower()
    text_word_set = set(_WORD_RE.findall(text))
    if not text_word_set:
        return 0.0

    matched_words = topic_words & text_word_set
    word_overlap = len(matched_words) / len(topic_words)

    if word_overlap < 0.5:
        return 0.0

    phrase_bonus = 1.5 if topic_lower in text else 1.0

    title_lower = title.lower()
    title_phrase_bonus = 2.0 if topic_lower in title_lower else 1.0
    title_word_set = set(w.lower() for w in _WORD_RE.findall(title))
    title_word_overlap = len(topic_words & title_word_set) / len(topic_words)
    title_bonus = max(title_phrase_bonus, 1.0 + title_word_overlap)

    recency_boost = 1.0
    if pub_date:
        age_hours = max((datetime.now(timezone.utc) - pub_date).total_seconds() / 3600, 1)
        recency_boost = 1.0 + (168 / age_hours) * 0.1

    return round(word_overlap * phrase_bonus * title_bonus * recency_boost, 2)


def parse_date(entry: dict) -> datetime | None:
    for field in ("published", "updated"):
        raw = entry.get(field)
        if not raw:
            continue
        try:
            return parsedate_to_datetime(raw)
        except Exception:
            pass
    return None


async def fetch_feed(client: httpx.AsyncClient, name: str, url: str) -> tuple[str, str]:
    try:
        resp = await client.get(url, follow_redirects=True)
        resp.raise_for_status()
        return name, resp.text
    except Exception:
        return name, ""
