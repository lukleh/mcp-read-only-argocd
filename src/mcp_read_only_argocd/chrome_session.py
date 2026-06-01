"""Load Argo CD browser session cookies from Chrome."""

from __future__ import annotations

import logging
from collections.abc import Iterable
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

ARGOCD_SESSION_COOKIE = "argocd.token"
CHROME_SUPPORT_DIR = Path("~/Library/Application Support/Google/Chrome").expanduser()
DEFAULT_CHROME_PROFILE = "Profile 1"


def extract_connection_domain(url: str) -> str:
    """Return the hostname used to match browser cookies for an Argo CD URL."""
    parsed = urlparse(url)
    if parsed.hostname:
        return parsed.hostname.lower().lstrip(".")

    fallback = url.split("://", 1)[-1]
    return fallback.split("/", 1)[0].split(":", 1)[0].lower().lstrip(".")


def _cookie_domain_matches(cookie_domain: str | None, connection_domain: str) -> bool:
    if not cookie_domain:
        return False

    normalized_cookie_domain = cookie_domain.lower().lstrip(".")
    return (
        normalized_cookie_domain == connection_domain
        or normalized_cookie_domain.endswith(f".{connection_domain}")
        or connection_domain.endswith(f".{normalized_cookie_domain}")
    )


def _load_chrome_cookie_jar(cookie_file: Path | None = None) -> Iterable[Any]:
    import browser_cookie3

    if cookie_file is None:
        return browser_cookie3.chrome()
    return browser_cookie3.chrome(cookie_file=str(cookie_file))


def _profile_cookie_file(profile_name: str = DEFAULT_CHROME_PROFILE) -> Path | None:
    cookie_file = CHROME_SUPPORT_DIR / profile_name / "Cookies"
    return cookie_file if cookie_file.exists() else None


def load_session_token_from_chrome(url: str) -> str | None:
    """Load the argocd.token cookie matching the given Argo CD URL from Chrome."""
    connection_domain = extract_connection_domain(url)
    if not connection_domain:
        return None

    cookie_file = _profile_cookie_file()
    try:
        cookies = _load_chrome_cookie_jar(cookie_file)
    except Exception as exc:
        logger.warning(
            "Failed to load Chrome cookies for %s: %s", connection_domain, exc
        )
        return None

    fallback_token: str | None = None
    for cookie in cookies:
        if cookie.name != ARGOCD_SESSION_COOKIE:
            continue

        cookie_domain = cookie.domain or ""
        if not _cookie_domain_matches(cookie_domain, connection_domain):
            continue

        normalized_cookie_domain = cookie_domain.lower().lstrip(".")
        if normalized_cookie_domain == connection_domain:
            logger.info(
                "Loaded Chrome Argo CD session cookie for %s", connection_domain
            )
            return cookie.value

        fallback_token = fallback_token or cookie.value

    if fallback_token:
        logger.info("Loaded Chrome Argo CD session cookie for %s", connection_domain)

    return fallback_token
