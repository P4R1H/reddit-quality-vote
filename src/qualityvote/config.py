"""Configuration loading.

Thresholds, message copy, the subreddit and the flair template id are all
supplied by the operator.
"""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path


class ConfigError(RuntimeError):
    """Raised when configuration is missing or malformed."""


def _require(mapping: dict, key: str, context: str):
    try:
        return mapping[key]
    except KeyError as exc:
        raise ConfigError(f"missing [{context}] key {key!r}") from exc


def _require_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise ConfigError(f"environment variable {name} is not set")
    return value


@dataclass(frozen=True)
class RedditCredentials:
    client_id: str
    client_secret: str
    username: str
    password: str
    user_agent: str

    @classmethod
    def from_env(cls) -> "RedditCredentials":
        username = _require_env("REDDIT_USERNAME")
        return cls(
            client_id=_require_env("REDDIT_CLIENT_ID"),
            client_secret=_require_env("REDDIT_CLIENT_SECRET"),
            username=username,
            password=_require_env("REDDIT_PASSWORD"),
            user_agent=os.environ.get("REDDIT_USER_AGENT", "reddit-quality-vote/1.0"),
        )


@dataclass(frozen=True)
class RedditSettings:
    subreddit: str
    poll_interval_seconds: int
    new_post_limit: int
    comment_scan_limit: int

    @classmethod
    def parse(cls, raw: dict) -> "RedditSettings":
        subreddit = str(_require(raw, "subreddit", "reddit")).strip().lstrip("/")
        if subreddit.startswith("r/"):
            subreddit = subreddit[2:]
        if not subreddit or subreddit == "your_subreddit":
            raise ConfigError("[reddit] subreddit must be set to a real subreddit")
        return cls(
            subreddit=subreddit,
            poll_interval_seconds=int(raw.get("poll_interval_seconds", 15)),
            new_post_limit=int(raw.get("new_post_limit", 50)),
            comment_scan_limit=int(raw.get("comment_scan_limit", 100)),
        )


@dataclass(frozen=True)
class VotingSettings:
    remove_at_score: int
    approve_at_score: int
    grace_period_minutes: int

    @classmethod
    def parse(cls, raw: dict) -> "VotingSettings":
        remove_at = int(raw.get("remove_at_score", -3))
        approve_at = int(raw.get("approve_at_score", 7))
        if remove_at >= approve_at:
            raise ConfigError(
                "[voting] remove_at_score must be below approve_at_score"
            )
        return cls(
            remove_at_score=remove_at,
            approve_at_score=approve_at,
            grace_period_minutes=int(raw.get("grace_period_minutes", 30)),
        )


@dataclass(frozen=True)
class Messages:
    prompt: str
    removed: str
    approved: str

    @classmethod
    def parse(cls, raw: dict) -> "Messages":
        prompt = str(_require(raw, "prompt", "messages")).strip()
        if not prompt:
            raise ConfigError("[messages] prompt must not be empty")
        return cls(
            prompt=prompt,
            removed=str(_require(raw, "removed", "messages")).strip(),
            approved=str(_require(raw, "approved", "messages")).strip(),
        )


@dataclass(frozen=True)
class Config:
    reddit: RedditSettings
    voting: VotingSettings
    messages: Messages
    removed_flair_template_id: str | None
    credentials: RedditCredentials

    @classmethod
    def load(cls, path: str | Path = "config.toml") -> "Config":
        config_path = Path(path)
        if not config_path.exists():
            raise ConfigError(
                f"{config_path} not found -- copy config.example.toml and fill it in"
            )
        with config_path.open("rb") as handle:
            raw = tomllib.load(handle)

        flair = str(raw.get("flair", {}).get("removed_template_id", "")).strip()
        return cls(
            reddit=RedditSettings.parse(_require(raw, "reddit", "root")),
            voting=VotingSettings.parse(raw.get("voting", {})),
            messages=Messages.parse(_require(raw, "messages", "root")),
            removed_flair_template_id=flair or None,
            credentials=RedditCredentials.from_env(),
        )
