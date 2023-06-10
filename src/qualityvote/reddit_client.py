"""praw client construction."""

from __future__ import annotations

import praw

from .config import RedditCredentials


def build_reddit(credentials: RedditCredentials) -> praw.Reddit:
    return praw.Reddit(
        client_id=credentials.client_id,
        client_secret=credentials.client_secret,
        username=credentials.username,
        password=credentials.password,
        user_agent=credentials.user_agent,
    )
