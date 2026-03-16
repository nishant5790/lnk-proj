"""Root entrypoint for deploying the MCP Trends REST API."""

from mcp_trends.api import app, main

__all__ = ["app"]


if __name__ == "__main__":
    main()
