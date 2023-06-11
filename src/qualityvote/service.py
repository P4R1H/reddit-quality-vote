"""The quality-vote loop.

Two independent passes run on every cycle:

1. *prompt* -- every new submission without one gets a stickied, distinguished
   comment inviting the community to vote on whether the post belongs.
2. *resolve* -- the bot's own recent prompt comments are re-read, and the score
   the community gave each one decides whether the post is approved or removed.

The signal is the score of a stickied comment, so the vote measures fit
independently of whether people enjoyed the post.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import prawcore

from .config import Config

log = logging.getLogger(__name__)


@dataclass
class CycleStats:
    prompted: int = 0
    approved: int = 0
    removed: int = 0
    pending: int = 0
    errors: int = 0

    def summary(self) -> str:
        return (
            f"prompted={self.prompted} approved={self.approved} "
            f"removed={self.removed} pending={self.pending} errors={self.errors}"
        )


class QualityVoteService:
    def __init__(self, reddit, config: Config, *, dry_run: bool = False) -> None:
        self.reddit = reddit
        self.config = config
        self.dry_run = dry_run
        self.username = config.credentials.username
        self.subreddit = reddit.subreddit(config.reddit.subreddit)
        self._me = reddit.redditor(self.username)

    # -- prompting ---------------------------------------------------------

    def _already_prompted(self, submission) -> bool:
        """True if our prompt comment is already on this submission.

        Only top-level comments are inspected. ``replace_more(limit=0)`` drops
        the "load more" placeholders instead of fetching them.
        """
        submission.comments.replace_more(limit=0)
        for comment in submission.comments:
            author = comment.author
            if author and author.name.lower() == self.username.lower():
                return True
        return False

    def _prompt(self, submission, stats: CycleStats) -> None:
        if submission.removed_by_category or submission.approved_by:
            return
        if self._already_prompted(submission):
            return

        if self.dry_run:
            log.info("[dry run] would prompt on %s", submission.id)
            stats.prompted += 1
            return

        comment = submission.reply(self.config.messages.prompt)
        comment.mod.distinguish(sticky=True)
        stats.prompted += 1
        log.info("prompted on %s", submission.id)

    def run_prompt_pass(self, stats: CycleStats) -> None:
        for submission in self.subreddit.new(limit=self.config.reddit.new_post_limit):
            try:
                self._prompt(submission, stats)
            except prawcore.exceptions.PrawcoreException:
                # One unavailable submission must not abandon the rest of the
                # listing, which is what an unscoped break used to do here.
                log.warning("could not prompt on %s", submission.id, exc_info=True)
                stats.errors += 1

    # -- resolving ---------------------------------------------------------

    def _is_prompt_comment(self, comment) -> bool:
        return comment.body.strip() == self.config.messages.prompt.strip()

    def _within_grace_period(self, comment) -> bool:
        age = datetime.now(timezone.utc) - datetime.fromtimestamp(
            comment.created_utc, tz=timezone.utc
        )
        return age < timedelta(minutes=self.config.voting.grace_period_minutes)

    def _apply_removal(self, comment) -> None:
        submission = comment.submission
        submission.mod.remove()
        if self.config.removed_flair_template_id:
            submission.flair.select(self.config.removed_flair_template_id)
        notice = submission.reply(self.config.messages.removed)
        notice.mod.distinguish(sticky=True)
        comment.mod.remove()
        log.info("removed %s by community vote", submission.id)

    def _apply_approval(self, comment) -> None:
        submission = comment.submission
        submission.mod.approve()
        notice = submission.reply(self.config.messages.approved)
        notice.mod.distinguish(sticky=True)
        comment.mod.remove()
        log.info("approved %s by community vote", submission.id)

    def _resolve(self, comment, stats: CycleStats) -> None:
        if not self._is_prompt_comment(comment) or comment.removed:
            return
        if self._within_grace_period(comment):
            stats.pending += 1
            return

        score = comment.score
        if score <= self.config.voting.remove_at_score:
            if self.dry_run:
                log.info("[dry run] would remove %s (score %d)", comment.submission.id, score)
            else:
                self._apply_removal(comment)
            stats.removed += 1
        elif score >= self.config.voting.approve_at_score:
            if self.dry_run:
                log.info("[dry run] would approve %s (score %d)", comment.submission.id, score)
            else:
                self._apply_approval(comment)
            stats.approved += 1
        else:
            stats.pending += 1

    def run_resolve_pass(self, stats: CycleStats) -> None:
        for comment in self._me.comments.new(limit=self.config.reddit.comment_scan_limit):
            try:
                self._resolve(comment, stats)
            except prawcore.exceptions.PrawcoreException:
                log.warning("could not resolve comment %s", comment.id, exc_info=True)
                stats.errors += 1

    # -- driver ------------------------------------------------------------

    def run_once(self) -> CycleStats:
        stats = CycleStats()
        self.run_prompt_pass(stats)
        self.run_resolve_pass(stats)
        log.info("cycle complete: %s", stats.summary())
        return stats

    def run_forever(self) -> None:
        while True:
            try:
                self.run_once()
            except prawcore.exceptions.PrawcoreException:
                log.exception("cycle failed, retrying after the poll interval")
            except KeyboardInterrupt:
                raise
            time.sleep(self.config.reddit.poll_interval_seconds)
