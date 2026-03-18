from __future__ import annotations

import re
from urllib.parse import urlparse, urlunparse

import requests

VALID_REDDIT_HOSTS = {
    "reddit.com",
    "www.reddit.com",
    "old.reddit.com",
    "m.reddit.com",
    "new.reddit.com",
    "sh.reddit.com",
    "redd.it",
    "www.redd.it",
}

USER_AGENT = "telegram-reddit-tldr-bot/1.0"


class InvalidRedditUrl(ValueError):
    pass


def is_reddit_post_url(value: str) -> bool:
    try:
        normalize_reddit_url(value)
        return True
    except InvalidRedditUrl:
        return False


def normalize_reddit_url(value: str, timeout: int = 15) -> str:
    if not value or not value.strip():
        raise InvalidRedditUrl("Prazan URL.")

    raw = value.strip()

    if not re.match(r"^https?://", raw, flags=re.IGNORECASE):
        raw = "https://" + raw

    parsed = urlparse(raw)

    if parsed.netloc.lower() not in VALID_REDDIT_HOSTS:
        raise InvalidRedditUrl("Ovo nije podržan Reddit URL.")

    resolved = _resolve_if_needed(raw, timeout=timeout)
    canonical = _canonicalize_reddit_post_url(resolved)

    if not canonical:
        raise InvalidRedditUrl("Nisam uspio prepoznati valjani Reddit post URL.")

    return canonical


def _resolve_if_needed(url: str, timeout: int = 15) -> str:
    parsed = urlparse(url)
    host = parsed.netloc.lower()
    path = parsed.path or ""
    query = parsed.query or ""

    should_resolve = (
        "/s/" in path
        or host in {"redd.it", "www.redd.it"}
        or "share_id=" in query
        or "utm_" in query
    )

    if not should_resolve:
        return url

    try:
        response = requests.get(
            url,
            headers={"User-Agent": USER_AGENT},
            timeout=timeout,
            allow_redirects=True,
        )
        return response.url or url
    except requests.RequestException:
        return url


def _canonicalize_reddit_post_url(url: str) -> str | None:
    parsed = urlparse(url)
    host = parsed.netloc.lower()
    path = parsed.path or ""

    if host in {"reddit.com", "old.reddit.com", "m.reddit.com", "new.reddit.com", "sh.reddit.com"}:
        host = "www.reddit.com"
    elif host == "www.reddit.com":
        pass
    elif host in {"redd.it", "www.redd.it"}:
        return None
    else:
        return None

    # standardni oblik:
    # /r/<subreddit>/comments/<post_id>/<slug>/
    match = re.match(
        r"^/r/(?P<subreddit>[^/]+)/comments/(?P<post_id>[a-z0-9]+)/(?P<slug>[^/?#]*)/?",
        path,
        flags=re.IGNORECASE,
    )
    if match:
        subreddit = match.group("subreddit")
        post_id = match.group("post_id")
        slug = match.group("slug") or ""
        clean_path = f"/r/{subreddit}/comments/{post_id}/{slug}/"
        return urlunparse(("https", host, clean_path, "", "", ""))

    # kraći oblik:
    # /comments/<post_id>/<slug>/
    match = re.match(
        r"^/comments/(?P<post_id>[a-z0-9]+)/(?P<slug>[^/?#]*)/?",
        path,
        flags=re.IGNORECASE,
    )
    if match:
        post_id = match.group("post_id")
        slug = match.group("slug") or ""
        clean_path = f"/comments/{post_id}/{slug}/"
        return urlunparse(("https", host, clean_path, "", "", ""))

    return None