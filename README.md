# MCP Trends Server

An MCP server that discovers trending topics across multiple sources using LangChain and Gemini.

## Sources

- **Hacker News** — Top stories via Algolia API
- **YouTube** — Trending videos via YouTube Data API v3
- **GitHub** — Trending repos via GitHub Search API
- **Google/LinkedIn** — LinkedIn posts via Gemini with Google Search grounding

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

3. Test the server:

   ```bash
   uv run python -m mcp_trends.server
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
| `aggregate_trends` | Query all sources + AI-generated trend summary |
