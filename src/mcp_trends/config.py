from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    google_api_key: str = ""
    youtube_api_key: str = ""

    http_timeout: int = 15
    gemini_timeout: int = 30
    default_limit: int = 10

    github_min_stars: int = 50
    youtube_min_views: int = 1000
    hackernews_min_points: int = 5

    api_host: str = "0.0.0.0"
    api_port: int = 8000

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
