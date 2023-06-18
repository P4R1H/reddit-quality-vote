# reddit-quality-vote

Lets a subreddit's own members decide whether a post belongs.

The bot stickies a distinguished comment on every new submission asking whether
the post fits the subreddit, then reads the score of that comment. Sink it and
the post is removed; upvote it and the post is approved.

## Design notes

The vote runs on a dedicated comment instead of the post's own score. A post
can be popular and still be off-topic, and the two signals get measured
separately this way.

A post is not judged until its prompt comment has had time to collect votes.
Without that delay a single early downvote decides the outcome.

Errors are caught per item, so an unavailable or already-removed post gets
logged and skipped. An earlier version broke out of the whole listing when it
hit one bad submission, which meant a single deleted post ended the pass.

Thresholds, message copy and the optional removal flair template all come from
config.

`--dry-run` logs every decision without acting, which is how you calibrate
thresholds against a live subreddit before letting the bot touch anything.

## Layout

```
main.py                        CLI entry point
src/qualityvote/
  config.py                    TOML structure + environment credentials, validated on load
  reddit_client.py             praw construction
  service.py                   the prompt pass and the resolve pass
```

## Setup

Needs Python 3.11 or newer, for `tomllib`. The bot account has to be a
moderator of the subreddit with `posts` and `flair` permissions.

```bash
pip install -r requirements.txt
cp config.example.toml config.toml
cp .env.example .env
```

| variable | purpose |
| --- | --- |
| `REDDIT_CLIENT_ID` | script app id |
| `REDDIT_CLIENT_SECRET` | script app secret |
| `REDDIT_USERNAME` | the bot's moderator account |
| `REDDIT_PASSWORD` | its password |
| `REDDIT_USER_AGENT` | optional, defaults to `reddit-quality-vote/1.0` |

Watch it decide without letting it act:

```bash
python main.py --once --dry-run
```

Then run it:

```bash
python main.py
```

## Tuning

`remove_at_score` and `approve_at_score` depend on how much your subreddit
votes. Start wide, watch a `--dry-run` for a day, then tighten. If posts sit
unresolved the thresholds are too far apart for your traffic. If posts get
decided within minutes, lengthen `grace_period_minutes`.

## Licence

MIT
