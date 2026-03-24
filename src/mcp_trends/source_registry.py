from __future__ import annotations

from pydantic import BaseModel, Field


class SourceMetadata(BaseModel):
    id: str = Field(description="Unique machine-readable identifier used in API paths and responses")
    name: str = Field(description="Human-readable display name")
    description: str = Field(
        description=(
            "What this source platform is, independent of our integration. "
            "Covers the platform's purpose, audience, content style, and what "
            "makes it uniquely valuable as a signal source."
        ),
    )
    integration: str = Field(
        description=(
            "How our system fetches, filters, ranks, and returns data from this "
            "source. Covers the upstream API used, the processing pipeline, "
            "deduplication, sorting strategy, and any fallback behaviours."
        ),
    )
    best_for: list[str] = Field(description="Query intents or use-cases where this source excels")
    content_type: str = Field(description="The type of content items returned (e.g. articles, videos, repos)")
    default_time_window: str = Field(description="How far back the source searches by default")
    supports_period_param: bool = Field(description="Whether the 'period' query parameter affects results")
    quality_signals: list[str] = Field(description="Metrics available in each result's metadata for ranking")
    quality_thresholds: dict[str, float | int | str] = Field(
        default_factory=dict,
        description="Minimum quality filters applied before results are returned",
    )
    result_metadata_fields: dict[str, str] = Field(
        description="Fields present in each TrendItem.metadata dict, with a short explanation of each",
    )
    requires_api_key: str | None = Field(
        default=None,
        description="Environment variable name of required API key, or null if no key needed",
    )
    rate_limited: bool = Field(description="Whether the upstream API enforces rate limits that may cause retries")
    api_endpoint: str = Field(description="The REST API path to call this source")
    example_queries: list[str] = Field(description="Representative topics that work well with this source")
    limitations: list[str] = Field(
        default_factory=list,
        description="Known caveats or blind spots an LLM should be aware of",
    )


SOURCE_REGISTRY: list[SourceMetadata] = [
    SourceMetadata(
        id="hackernews",
        name="Hacker News",
        description=(
            "Hacker News (news.ycombinator.com) is a social news site run by Y Combinator, "
            "focused on technology, startups, and intellectual curiosity. Its audience is "
            "primarily software engineers, founders, researchers, and tech-savvy professionals. "
            "Users submit links or self-posts ('Ask HN', 'Show HN') and the community upvotes "
            "and discusses them. Content that surfaces here tends to be technically deep, "
            "contrarian, or early-signal — stories often appear on HN days before mainstream "
            "coverage. The discussion threads are frequently more valuable than the linked "
            "article itself, as domain experts weigh in with nuanced takes."
        ),
        integration=(
            "Fetches stories from the Algolia HN Search API (hn.algolia.com/api/v1/search_by_date), "
            "filtered by a configurable time window (week/month/quarter). Results are deduplicated "
            "by URL. A quality filter removes stories below 5 points; if no stories pass, "
            "unfiltered results are returned as a fallback. Final results are sorted by points "
            "descending. Each item includes an engagement_ratio (comments/points) as a proxy for "
            "how controversial or discussion-worthy a story is."
        ),
        best_for=[
            "Developer and engineering community sentiment",
            "Early signals on new tools, frameworks, or libraries",
            "Technical deep-dives and Show HN launches",
            "Startup and open-source project announcements",
            "Controversial or polarizing tech opinions",
        ],
        content_type="Story links with discussion threads",
        default_time_window="7 days (configurable via period: week | month | quarter)",
        supports_period_param=True,
        quality_signals=["points", "num_comments", "engagement_ratio"],
        quality_thresholds={"min_points": 5},
        result_metadata_fields={
            "points": "Upvote count — primary popularity signal",
            "num_comments": "Number of discussion comments",
            "engagement_ratio": "comments / points — high values suggest controversial or thought-provoking content",
            "discussion_url": "Direct link to the HN discussion thread",
            "author": "HN username who submitted the story",
            "created_at": "ISO timestamp of submission",
        },
        requires_api_key=None,
        rate_limited=False,
        api_endpoint="/trends/hackernews",
        example_queries=["AI Engineer", "Rust vs Go", "LLM fine-tuning", "YC startup"],
        limitations=[
            "Strongly biased toward software engineering, startups, and Silicon Valley culture",
            "Non-technical topics (marketing, sales, design) get very low coverage",
            "No engagement metrics beyond points and comments (no views, impressions)",
            "If no stories meet the 5-point minimum, unfiltered low-quality results are returned instead of an empty set",
        ],
    ),
    SourceMetadata(
        id="youtube",
        name="YouTube",
        description=(
            "YouTube is the world's largest video-sharing platform with over 2 billion monthly "
            "users. Content spans every category — tutorials, vlogs, keynotes, podcasts, product "
            "reviews, entertainment, and more. For trend research, YouTube is uniquely valuable "
            "because video creators often translate complex ideas into accessible formats, and "
            "engagement metrics (views, likes, comments) provide strong signals of audience "
            "resonance. Channels range from individual creators to major media outlets, making "
            "it a cross-section of both grassroots and institutional perspectives."
        ),
        integration=(
            "Uses the YouTube Data API v3. First searches for videos matching the topic published "
            "in the last 7 days (ordered by view count). Then fetches detailed statistics (views, "
            "likes, comments) for each video via a second API call. Videos below 1,000 views are "
            "discarded. Results are deduplicated by (title, channel) to remove re-uploads. Final "
            "ranking is by like_ratio_pct (likes/views * 100) so that highly-liked content "
            "surfaces first, not just the most-viewed. Retries on 429/5xx with exponential backoff."
        ),
        best_for=[
            "Video tutorials and how-to content",
            "Thought-leader opinions and keynote talks",
            "Product demos, reviews, and walkthroughs",
            "Visual explainers of complex topics",
            "Identifying rising content creators in a niche",
        ],
        content_type="YouTube videos with engagement statistics",
        default_time_window="7 days",
        supports_period_param=False,
        quality_signals=["view_count", "like_count", "comment_count", "like_ratio_pct"],
        quality_thresholds={"min_views": 1000},
        result_metadata_fields={
            "channel": "YouTube channel name that published the video",
            "view_count": "Total number of views",
            "like_count": "Total number of likes",
            "comment_count": "Total number of comments",
            "like_ratio_pct": "Likes as a percentage of views — high ratio means audience loved it",
            "published_at": "ISO timestamp when the video was published",
            "description": "Video description text (may be truncated)",
        },
        requires_api_key="YOUTUBE_API_KEY",
        rate_limited=True,
        api_endpoint="/trends/youtube",
        example_queries=["AI agents tutorial", "system design interview", "Next.js 15 features"],
        limitations=[
            "Requires YOUTUBE_API_KEY to function",
            "API quota limits may throttle high-frequency usage",
            "Only searches the last 7 days (no configurable period)",
            "Shorts and long-form videos are mixed together",
        ],
    ),
    SourceMetadata(
        id="github",
        name="GitHub",
        description=(
            "GitHub is the dominant platform for open-source software development, hosting over "
            "200 million repositories. Developers use it to publish code, collaborate via pull "
            "requests, and track issues. A repository's star count is a community endorsement "
            "signal — rapidly-starred repos indicate genuine developer interest. GitHub is the "
            "primary place to track which tools, libraries, and frameworks are gaining real "
            "adoption, what languages are trending, and which projects the developer community "
            "is excited about. Unlike social platforms, engagement here (stars, forks, issues) "
            "represents actual usage intent, not just commentary."
        ),
        integration=(
            "Queries the GitHub REST API (api.github.com/search/repositories) for repos matching "
            "the topic that have been pushed to in the last 7 days. Fetches up to 3x the "
            "requested limit, then filters out repos with fewer than 50 stars. Calculates a "
            "stars_per_day growth velocity metric (total stars / repo age in days) and sorts by "
            "it descending, so fast-rising projects rank above established-but-stagnant ones. "
            "Unauthenticated requests — subject to GitHub's 10 req/min rate limit."
        ),
        best_for=[
            "Trending open-source projects and tools",
            "New framework and library releases",
            "Developer tooling adoption signals",
            "Language and ecosystem popularity shifts",
            "Finding code examples and reference implementations",
        ],
        content_type="GitHub repositories with star/fork statistics",
        default_time_window="7 days (repos with recent pushes)",
        supports_period_param=False,
        quality_signals=["stars", "forks", "stars_per_day", "open_issues"],
        quality_thresholds={"min_stars": 50},
        result_metadata_fields={
            "description": "Repository description",
            "stars": "Total stargazer count",
            "forks": "Total fork count",
            "open_issues": "Number of open issues",
            "stars_per_day": "Stars divided by repo age in days — measures growth velocity",
            "language": "Primary programming language",
            "topics": "GitHub topic tags (up to 10)",
            "license": "SPDX license identifier",
            "created_at": "ISO timestamp when the repo was created",
            "updated_at": "ISO timestamp of last update",
        },
        requires_api_key=None,
        rate_limited=True,
        api_endpoint="/trends/github",
        example_queries=["vector database", "LLM framework", "Kubernetes operator", "Rust web framework"],
        limitations=[
            "Only surfaces repositories, not issues, PRs, or discussions",
            "Minimum 50 stars threshold may exclude very new but promising projects",
            "Unauthenticated requests are limited to 10 req/min by GitHub",
            "No configurable period — always looks at repos pushed in the last 7 days",
        ],
    ),
    SourceMetadata(
        id="google_linkedin",
        name="LinkedIn",
        description=(
            "LinkedIn is the world's largest professional networking platform with over 1 billion "
            "members. Its content feed features posts and articles from executives, industry "
            "analysts, hiring managers, and thought leaders. Content tends to be professional, "
            "opinion-driven, and business-oriented — covering career advice, industry analysis, "
            "hiring trends, product launches, and B2B strategy. LinkedIn posts often reflect the "
            "corporate and professional consensus on a topic, making it valuable for understanding "
            "how industries frame narratives. Engagement types are distinctive: opinion pieces, "
            "data-driven analyses, contrarian takes, and storytelling dominate the feed."
        ),
        integration=(
            "Since LinkedIn has no public search API, this source uses Gemini 2.0 Flash with "
            "Google Search grounding to search 'site:linkedin.com' for the topic. The LLM "
            "returns structured JSON with title, URL, author, engagement_type, key_takeaway, "
            "and summary for each result. URLs that pass through Google's grounding redirect "
            "are resolved to final LinkedIn URLs. If the LLM output cannot be parsed as JSON, "
            "a single fallback item with the raw_response metadata field is returned. Requires "
            "GOOGLE_API_KEY (the same key used for the Gemini summarizer)."
        ),
        best_for=[
            "Professional and B2B industry discourse",
            "Thought leadership and executive perspectives",
            "Career and hiring trend discussions",
            "Industry-specific hot takes and contrarian views",
            "LinkedIn content strategy and engagement patterns",
        ],
        content_type="LinkedIn posts and articles with AI-extracted insights",
        default_time_window="~7 days (guided by prompt, not strict filter)",
        supports_period_param=False,
        quality_signals=[],
        quality_thresholds={},
        result_metadata_fields={
            "author": "LinkedIn post author name",
            "engagement_type": "Classified as: opinion | data-driven | how-to | contrarian | storytelling | news-reaction",
            "key_takeaway": "The single most interesting or surprising claim from the post",
            "summary": "1-2 sentence summary of the post content",
            "raw_response": "Present only in fallback results when JSON parsing fails — contains raw LLM output",
        },
        requires_api_key="GOOGLE_API_KEY",
        rate_limited=True,
        api_endpoint="/trends/google-linkedin",
        example_queries=["AI in hiring", "remote work debate", "SaaS pricing strategy", "GenAI enterprise adoption"],
        limitations=[
            "Results are LLM-generated; URLs may occasionally be hallucinated or stale",
            "No direct engagement metrics (likes, comments, shares) — relies on LLM judgment",
            "No numeric quality signals — results cannot be ranked by a metric, only by LLM-assigned categories",
            "Slower than direct-API sources due to LLM inference step",
            "Cannot access LinkedIn-gated content; relies on public-facing data via Google",
            "Uses the same GOOGLE_API_KEY as the Gemini summarizer (not a separate LinkedIn credential)",
            "If LLM output cannot be parsed as JSON, a single fallback item with raw_response metadata is returned",
        ],
    ),
    SourceMetadata(
        id="reddit",
        name="Reddit",
        description=(
            "Reddit is a network of over 100,000 communities (subreddits), each focused on a "
            "specific topic — from r/MachineLearning to r/startups to r/ExperiencedDevs. Users "
            "submit posts (links or text) and the community votes them up or down. Reddit's "
            "unique value is unfiltered, pseudonymous opinion: people say things here they "
            "wouldn't on LinkedIn or Twitter. Subreddit context tells you which community cares "
            "about a topic. The upvote ratio reveals consensus vs controversy — a post at 0.55 "
            "upvote ratio is deeply divisive, while 0.95+ is near-universal agreement. Reddit "
            "is where you find real user complaints, honest product comparisons, and grassroots "
            "sentiment before it hits mainstream media."
        ),
        integration=(
            "Queries Reddit's public JSON API (reddit.com/search.json) with the topic as search "
            "term. Default sort is 'hot', with a configurable time filter (week/month/quarter "
            "mapped to Reddit's time parameters). Fetches up to 3x the limit (max 100). Posts "
            "below a score of 10 are discarded. Results are ranked by score * upvote_ratio — a "
            "compound signal that rewards high-score posts with strong community consensus. "
            "Self-text is truncated to 300 characters. Retries on 429 with exponential backoff "
            "(up to 3 attempts)."
        ),
        best_for=[
            "Grassroots community opinions and sentiment",
            "Product and tool comparisons (e.g. 'X vs Y')",
            "Real user feedback, complaints, and praise",
            "Niche community discussions (subreddit-specific)",
            "Controversial takes and crowd-sourced recommendations",
        ],
        content_type="Reddit posts with discussion metadata",
        default_time_window="7 days (configurable via period: week | month | quarter)",
        supports_period_param=True,
        quality_signals=["score", "num_comments", "upvote_ratio", "score_x_upvote_ratio (compound ranking key)"],
        quality_thresholds={"min_score": 10},
        result_metadata_fields={
            "score": "Net upvotes (upvotes minus downvotes)",
            "num_comments": "Total comment count on the post",
            "upvote_ratio": "Fraction of votes that are upvotes (0.0–1.0) — values near 0.5 indicate controversy",
            "subreddit": "Subreddit where the post was made (gives community context)",
            "author": "Reddit username of the poster",
            "created_utc": "ISO timestamp of post creation",
            "selftext": "First 300 characters of self-post text (empty for link posts)",
        },
        requires_api_key=None,
        rate_limited=True,
        api_endpoint="/trends/reddit",
        example_queries=["best IDE for Python", "Claude vs GPT", "startup burnout", "home lab setup"],
        limitations=[
            "Rate limited (429 responses trigger retry with backoff)",
            "Only returns posts, not individual comments",
            "Self-text is truncated to 300 characters",
            "Results can skew toward entertainment or meme-heavy subreddits for broad topics",
        ],
    ),
    SourceMetadata(
        id="rss",
        name="RSS Feeds (Curated Tech Publications)",
        description=(
            "A curated set of 7 major tech and business publications: TechCrunch, The Verge, "
            "Ars Technica, HubSpot, SaaStr, First Round Review, and Hacker Noon. These are "
            "established editorial outlets with professional journalists and editors — content "
            "here is vetted, well-written, and authoritative. TechCrunch and The Verge cover "
            "broad tech news; Ars Technica goes deep on technical analysis; HubSpot and SaaStr "
            "focus on B2B marketing and SaaS strategy; First Round Review publishes long-form "
            "startup operator advice; Hacker Noon is community-driven tech blogging. Together "
            "they represent the 'professional media' layer of tech discourse."
        ),
        integration=(
            "Fetches all 7 RSS/Atom feeds in parallel using httpx, then parses them with "
            "feedparser. Each article is scored for relevance to the topic using keyword "
            "matching against title and summary, weighted by recency. Articles older than "
            "7 days or below a relevance score of 0.5 are discarded. Results are sorted by "
            "relevance_score descending. Category tags from the feed are included (up to 5 "
            "per article). Summaries are truncated to 500 characters."
        ),
        best_for=[
            "Authoritative industry news and analysis",
            "Long-form editorial content and features",
            "Tech product launches and announcements",
            "Business strategy and SaaS insights",
            "Content from established, trusted publications",
        ],
        content_type="Published articles from tech and business blogs",
        default_time_window="7 days",
        supports_period_param=False,
        quality_signals=["relevance_score"],
        quality_thresholds={"min_relevance_score": 0.5},
        result_metadata_fields={
            "publication": "Name of the publishing site (e.g. TechCrunch, The Verge)",
            "published_date": "ISO timestamp of article publication",
            "summary": "Article summary or excerpt (up to 500 characters)",
            "relevance_score": "Computed score based on keyword match and recency (higher is better)",
            "categories": "Article category/topic tags from the feed (up to 5)",
        },
        requires_api_key=None,
        rate_limited=False,
        api_endpoint="/trends/rss",
        example_queries=["AI regulation", "SaaS metrics", "Apple WWDC", "cybersecurity breach"],
        limitations=[
            "Limited to 7 curated feeds — won't surface content from unlisted publications",
            "No engagement metrics (no views, shares, or comments)",
            "Relevance scoring is keyword-based, not semantic — may miss related but differently-worded articles",
            "Feed availability depends on publisher uptime",
        ],
    ),
    SourceMetadata(
        id="google_news",
        name="Google News",
        description=(
            "Google News is Google's news aggregation service that crawls thousands of "
            "publishers worldwide — from Reuters and BBC to niche trade publications. It "
            "algorithmically selects and ranks stories by relevance, freshness, and source "
            "authority. Unlike the curated RSS source which is limited to 7 tech outlets, "
            "Google News covers every industry and geography. It's the best signal for how "
            "mainstream and trade media are framing a topic, which outlets are covering it, "
            "and whether a story has broken out beyond the tech bubble."
        ),
        integration=(
            "Fetches the Google News RSS search feed (news.google.com/rss/search) for the "
            "topic with US/English locale. Parses the feed with feedparser. Each article is "
            "scored for relevance using the same keyword + recency algorithm as the RSS source "
            "(shares the rss_min_relevance_score threshold of 0.5). Articles older than 7 days "
            "or below the threshold are discarded. Results are sorted by relevance_score "
            "descending. The source outlet name is extracted from the feed entry metadata."
        ),
        best_for=[
            "Mainstream media coverage and press mentions",
            "Breaking news and real-time event tracking",
            "Cross-industry topic coverage",
            "Tracking narrative framing across multiple outlets",
            "Discovering which publications are covering a topic",
        ],
        content_type="News articles aggregated from multiple publishers",
        default_time_window="7 days",
        supports_period_param=False,
        quality_signals=["relevance_score"],
        quality_thresholds={"min_relevance_score": 0.5},
        result_metadata_fields={
            "publication": "Name of the source outlet (e.g. Reuters, BBC, TechCrunch)",
            "published_date": "ISO timestamp of article publication",
            "summary": "Article summary or lede (up to 500 characters)",
            "relevance_score": "Computed relevance score based on keyword match and recency",
        },
        requires_api_key=None,
        rate_limited=False,
        api_endpoint="/trends/google-news",
        example_queries=["OpenAI funding", "EU AI Act", "Tesla earnings", "climate tech investment"],
        limitations=[
            "Google News RSS may not include all articles shown on the web version",
            "No engagement metrics — cannot tell which articles got the most reads or shares",
            "Relevance scoring is keyword-based, not semantic",
            "Some articles may be behind paywalls",
            "Shares the same min_relevance_score threshold (0.5) as the RSS source — not independently tunable",
        ],
    ),
    SourceMetadata(
        id="podcasts",
        name="Podcasts (Apple Podcasts catalog)",
        description=(
            "Apple Podcasts is one of the two largest podcast directories globally (alongside "
            "Spotify), indexing over 2.5 million shows across every conceivable topic. Podcasts "
            "as a medium offer long-form, conversational depth that other sources can't match — "
            "a 60-minute interview with a domain expert contains insights you won't find in a "
            "tweet or blog post. They're particularly strong for industry insider perspectives, "
            "nuanced analysis, and emerging narratives that haven't yet been written up as "
            "articles. Episode metadata (show name, artist, genre, episode count) provides "
            "signals about the authority and maturity of the source."
        ),
        integration=(
            "Two-step pipeline: first discovers relevant podcast shows via the iTunes Search API "
            "(itunes.apple.com/search), then fetches each show's RSS feed to find recent episodes. "
            "Episodes are scored using a combined relevance signal: max(episode_score, show_baseline) "
            "+ episode_score, where show_baseline is the show-level relevance (minimum 3.0). "
            "Uses a 14-day window (longer than other sources since podcasts publish less frequently). "
            "Results are deduplicated by title and sorted by relevance_score descending. "
            "No retry logic — iTunes API errors surface directly."
        ),
        best_for=[
            "Long-form expert interviews and deep dives",
            "Industry insider conversations",
            "Narrative storytelling about a topic",
            "Learning-oriented content (courses, tutorials in audio)",
            "Discovering niche shows and emerging voices",
        ],
        content_type="Podcast episodes with show metadata",
        default_time_window="14 days",
        supports_period_param=False,
        quality_signals=["relevance_score", "episode_count"],
        quality_thresholds={},
        result_metadata_fields={
            "podcast_name": "Name of the podcast show",
            "artist": "Podcast creator or host name",
            "genre": "Primary genre from iTunes classification",
            "description": "Episode description (up to 300 characters)",
            "published_date": "ISO timestamp of episode publication",
            "relevance_score": "Combined show + episode relevance score",
            "episode_count": "Total number of episodes in the show (proxy for maturity)",
        },
        requires_api_key=None,
        rate_limited=True,
        api_endpoint="/trends/podcasts",
        example_queries=["AI engineering", "product management", "venture capital", "developer experience"],
        limitations=[
            "Only searches Apple Podcasts catalog — Spotify-exclusive shows are missed",
            "Uses a 14-day window (longer than other sources) since podcasts publish less frequently",
            "No listen/download counts — popularity is inferred from show metadata and relevance score",
            "Feed parsing depends on podcast publishers keeping their RSS feeds valid",
            "iTunes API may rate-limit requests but no automatic retry is implemented — errors surface directly",
        ],
    ),
]
