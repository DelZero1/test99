from __future__ import annotations

from urllib.parse import urlparse

VALID_REDDIT_HOSTS = {
    "reddit.com",
    "www.reddit.com",
    "old.reddit.com",
    "m.reddit.com",
}


def is_reddit_post_url(value: str) -> bool:
    try:
        parsed = urlparse(value.strip())
    except ValueError:
        return False

    if parsed.scheme not in {"http", "https"}:
        return False
    if parsed.netloc.lower() not in VALID_REDDIT_HOSTS:
        return False
    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) < 4:
        return False
    return parts[0] == "r" and parts[2] == "comments"
