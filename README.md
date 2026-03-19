# MCP Trends Server

An MCP server that discovers trending topics across 8 sources using LangChain and Gemini — built for LinkedIn content strategy.

## Sources

| # | Source | Auth | What it surfaces |
|---|--------|------|------------------|
| 1 | **Hacker News** | None | Developer/founder sentiment via Algolia API |
| 2 | **YouTube** | API key | Trending videos via YouTube Data API v3 |
| 3 | **GitHub** | None | Fastest-growing repos via GitHub Search API |
| 4 | **LinkedIn** | Gemini API key | LinkedIn posts via Gemini + Google Search grounding |
| 5 | **Reddit** | None | Community discussions via public JSON API |
| 6 | **RSS Feeds** | None | Curated publications (TechCrunch, SaaStr, HubSpot, etc.) |
| 7 | **Google News** | None | Breaking news from thousands of publications |
| 8 | **Podcasts** | None | Thought leader episodes via iTunes + RSS |

## Setup

1. Clone and install:

   ```bash
   uv venv && uv pip install -e .
   ```

2. Copy `.env.example` to `.env` and fill in your API keys:

   ```bash
   cp .env.example .env
   ```

   Required keys:
   - `GOOGLE_API_KEY` — Get from [Google AI Studio](https://aistudio.google.com/apikey)
   - `YOUTUBE_API_KEY` — Get from [Google Cloud Console](https://console.cloud.google.com/apis/credentials)

   No API keys needed for: Hacker News, GitHub, Reddit, RSS, Google News, Podcasts.

3. Test the server:

   ```bash
   uv run python test_local.py
   ```

## Deploy as REST API

This project also includes a FastAPI wrapper so you can deploy it as a regular HTTP API.

Run locally:

```bash
uv run mcp-trends-api
```

The API starts on `http://0.0.0.0:8000` by default (configurable via `.env`):

- `API_HOST` (default: `0.0.0.0`)
- `API_PORT` (default: `8000`)

Interactive docs:

- Swagger UI: `http://localhost:8000/docs`

Main endpoints:

- `POST /trends/hackernews`
- `POST /trends/youtube`
- `POST /trends/github`
- `POST /trends/google-linkedin`
- `POST /trends/reddit`
- `POST /trends/rss`
- `POST /trends/google-news`
- `POST /trends/podcasts`
- `POST /trends/aggregate` — All 8 sources + AI summary
- `GET /trends/{source}?topic=...&limit=...`

Example request:

```bash
curl -X POST http://localhost:8000/trends/aggregate \
  -H "Content-Type: application/json" \
  -d '{"topic":"AI Engineer","limit":5,"period":"week"}'
```

## MCP Client Configuration

### Cursor

Add to your Cursor MCP settings:

```json
{
  "mcpServers": {
    "trends": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/mcp-topics", "python", "-m", "mcp_trends.server"]
    }
  }
}
```

### Claude Desktop

Add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "trends": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/mcp-topics", "python", "-m", "mcp_trends.server"]
    }
  }
}
```

## Available Tools

| Tool | Description |
|------|-------------|
| `find_hackernews_trends` | Search Hacker News for trending stories |
| `find_youtube_trends` | Search YouTube for trending videos (last 7 days) |
| `find_github_trends` | Search GitHub for trending repositories |
| `find_google_linkedin_trends` | Search LinkedIn via Gemini + Google Search |
| `find_reddit_trends` | Search Reddit for trending discussions |
| `find_rss_trends` | Search curated industry publications |
| `find_google_news_trends` | Search Google News for breaking articles |
| `find_podcast_trends` | Search podcasts for trending episodes |
| `aggregate_trends` | Query all 8 sources + AI-generated trend summary |

## Summarizer Intelligence

The AI summarizer (Gemini 2.0 Flash) applies three ranking strategies:

- **Cross-platform signal detection** — Stories appearing in 2+ sources are auto-promoted to top trends
- **GitHub velocity surfacing** — Fastest-growing repos (by stars/day) are highlighted as primary evidence
- **Source-aware analysis** — Each source type is interpreted differently (e.g., podcast signals indicate trends 2-4 weeks before they hit LinkedIn)
